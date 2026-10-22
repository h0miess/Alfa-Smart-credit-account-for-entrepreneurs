"""Кредитная политика: из скоринга и данных заявки -> кредитное решение.

Скоринг (PD) говорит только об уровне риска. Решение учитывает ещё продукт,
сумму и срок, стоп-факторы, платёжеспособность и обеспечение. Поэтому один
и тот же PD может дать одобрение на одном продукте и встречное предложение
на другом — как и описано в кейсе.

Порядок: стоп-факторы -> запрос данных -> скоринг -> грейд -> лимит ->
ручная проверка -> одобрение / встречное предложение / отказ.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from enum import Enum

import pandas as pd

from .features import annuity_payment, max_principal_for_payment
from .model import ScoringModel, ScoreResult

POLICY_VERSION = "policy-2026.10-1"


def key_rate() -> float:
    """Ключевая ставка ЦБ, % годовых. Задаётся через env, чтобы обновлять без релиза."""
    return float(os.environ.get("KEY_RATE", "16.0"))


class Outcome(str, Enum):
    APPROVED = "APPROVED"
    COUNTER_OFFER = "COUNTER_OFFER"
    REQUEST_INFO = "REQUEST_INFO"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    DECLINED = "DECLINED"


# Грейды риска по калиброванному PD (верхняя граница, не включая).
GRADES = [("A", 0.02), ("B", 0.04), ("C", 0.08), ("D", 0.15), ("E", 1.01)]
# Надбавка к ключевой ставке, п.п.
GRADE_SPREAD = {"A": 3.0, "B": 5.0, "C": 7.5, "D": 10.0}
# Доля оборотов по счёту, которую можно направить на все платежи по долгам.
GRADE_MAX_DSR = {"A": 0.40, "B": 0.35, "C": 0.30, "D": 0.22}


@dataclass(frozen=True)
class Product:
    code: str
    name: str
    min_amount: float
    max_amount: float
    min_term: int
    max_term: int
    rate_adj: float  # поправка к ставке, п.п.
    turnover_cap: float | None  # лимит в оборотах в месяц (для беззалоговых)
    secured_from: float | None  # с какой суммы обязателен залог


PRODUCTS = {
    "express": Product("express", "Экспресс-кредит на оборотные средства",
                       100_000, 10_000_000, 3, 36, 0.0, 3.0, None),
    "overdraft": Product("overdraft", "Овердрафт к расчётному счёту",
                         50_000, 15_000_000, 12, 12, 1.0, 0.5, None),
    "investment": Product("investment", "Инвестиционный кредит",
                          1_000_000, 100_000_000, 12, 84, -1.5, None, 5_000_000),
}

MANUAL_REVIEW_AMOUNT = 30_000_000
MIN_COLLATERAL_COVERAGE = 0.7
SMB_REVENUE_LIMIT = 800_000_000


@dataclass
class Reason:
    code: str
    text: str


@dataclass
class Offer:
    product: str
    product_name: str
    amount: float
    term_months: int
    rate: float
    monthly_payment: float


@dataclass
class Decision:
    outcome: Outcome
    pd: float | None
    score: int | None
    grade: str | None
    max_amount: float | None
    offer: Offer | None
    reasons: list[Reason] = field(default_factory=list)
    risk_factors: list[dict] = field(default_factory=list)
    positive_factors: list[dict] = field(default_factory=list)
    requested_documents: list[str] = field(default_factory=list)
    model_version: str | None = None
    policy_version: str = POLICY_VERSION

    def to_dict(self) -> dict:
        d = asdict(self)
        d["outcome"] = self.outcome.value
        return d


def grade_for(pd_value: float) -> str:
    for g, upper in GRADES:
        if pd_value < upper:
            return g
    return "E"


def rate_for(grade: str, product: Product, collateral_coverage: float) -> float:
    r = key_rate() + GRADE_SPREAD[grade] + product.rate_adj
    if collateral_coverage >= 1.0:
        r -= 1.0
    return round(r, 2)


def credit_limit(app: dict, grade: str, product: Product, term: int, rate: float) -> float:
    """Максимальная сумма, которую клиент обслужит, с учётом всех ограничений продукта."""
    turnover = max(float(app["avg_monthly_turnover"]), 0.0)
    free_payment = GRADE_MAX_DSR[grade] * turnover - float(app["monthly_debt_payments"])
    if free_payment <= 0:
        return 0.0
    limit = max_principal_for_payment(free_payment, rate / 100.0, term)
    limit = min(limit, product.max_amount)
    if product.turnover_cap is not None:
        cap = product.turnover_cap * turnover
        if product.code == "overdraft":
            cap *= {"A": 1.0, "B": 1.0, "C": 0.7, "D": 0.4}[grade]
        limit = min(limit, cap)
    if product.secured_from is not None:
        by_collateral = float(app["collateral_value"]) / MIN_COLLATERAL_COVERAGE
        limit = min(limit, max(product.secured_from, by_collateral))
    return float(int(limit // 10_000) * 10_000)


def _stop_factors(app: dict) -> list[Reason]:
    r = []
    if app["business_age_months"] < 3:
        r.append(Reason("STOP_YOUNG_BUSINESS", "Бизнес работает меньше 3 месяцев"))
    if app["max_overdue_days_12m"] > 90:
        r.append(Reason("STOP_OVERDUE_90", "Просрочка более 90 дней за последние 12 месяцев"))
    if app["annual_revenue"] > SMB_REVENUE_LIMIT:
        r.append(Reason("STOP_NOT_SMB", "Выручка выше порога малого бизнеса — нужен другой продукт"))
    return r


def _info_requests(app: dict) -> tuple[list[Reason], list[str]]:
    reasons, docs = [], []
    if app["tax_arrears"]:
        reasons.append(Reason("INFO_TAX_ARREARS", "По данным ФНС есть задолженность по налогам"))
        docs.append("Справка ФНС об исполнении обязанности по уплате налогов или подтверждение погашения")
    turnover_share = app["avg_monthly_turnover"] * 12 / max(app["annual_revenue"], 1)
    if turnover_share < 0.2:
        reasons.append(Reason("INFO_LOW_TURNOVER", "Через счёт в банке проходит малая часть выручки"))
        docs.append("Выписка по счетам в других банках за 12 месяцев")
    product = PRODUCTS[app["product"]]
    if (product.secured_from is not None and app["requested_amount"] > product.secured_from
            and app["collateral_value"] <= 0):
        reasons.append(Reason("INFO_NO_COLLATERAL", "Для этой суммы нужен залог"))
        docs.append("Сведения о предлагаемом залоге (объект, оценочная стоимость)")
    return reasons, docs


def _manual_review(app: dict, grade: str, pd_value: float) -> list[Reason]:
    r = []
    if app["requested_amount"] > MANUAL_REVIEW_AMOUNT:
        r.append(Reason("MR_LARGE_AMOUNT", "Крупная сумма — решение принимает кредитный комитет"))
    if app["mass_address"]:
        r.append(Reason("MR_MASS_ADDRESS", "Адрес массовой регистрации — нужна проверка андеррайтером"))
    if app["director_changes_12m"] >= 2:
        r.append(Reason("MR_DIRECTOR_CHANGES", "Частая смена руководителя"))
    if grade == "D" and app["requested_amount"] > 3_000_000:
        r.append(Reason("MR_HIGH_RISK_AMOUNT", "Повышенный риск при заметной сумме"))
    if app["bki_history_months"] == 0 and app["requested_amount"] > 5_000_000:
        r.append(Reason("MR_NO_HISTORY", "Нет кредитной истории при крупной сумме"))
    return r


def decide(app: dict, scored: ScoreResult | None, model_version: str | None = None) -> Decision:
    """Чистая функция политики. scored=None, если до скоринга не дошли."""
    product = PRODUCTS[app["product"]]
    base = dict(model_version=model_version)

    stops = _stop_factors(app)
    if stops:
        return Decision(Outcome.DECLINED, None, None, None, None, None, reasons=stops, **base)

    info, docs = _info_requests(app)
    if info:
        return Decision(Outcome.REQUEST_INFO, None, None, None, None, None,
                        reasons=info, requested_documents=docs, **base)

    assert scored is not None
    pd_value, grade = scored.pd, grade_for(scored.pd)
    common = dict(
        pd=round(pd_value, 4), score=scored.score, grade=grade,
        risk_factors=[asdict(f) for f in scored.risk_factors],
        positive_factors=[asdict(f) for f in scored.positive_factors],
        **base,
    )

    if grade == "E":
        return Decision(Outcome.DECLINED, max_amount=None, offer=None,
                        reasons=[Reason("RISK_TOO_HIGH", "Оценка риска выше допустимой для продукта")],
                        **common)

    amount = float(app["requested_amount"])
    term = int(min(max(app["term_months"], product.min_term), product.max_term))
    coll_cov = float(app["collateral_value"]) / max(amount, 1.0)
    rate = rate_for(grade, product, coll_cov)
    limit = credit_limit(app, grade, product, term, rate)

    mr = _manual_review(app, grade, pd_value)
    if mr:
        offer = _make_offer(product, min(amount, limit), term, rate) if limit >= product.min_amount else None
        return Decision(Outcome.MANUAL_REVIEW, max_amount=limit, offer=offer, reasons=mr, **common)

    if amount <= limit:
        return Decision(Outcome.APPROVED, max_amount=limit, offer=_make_offer(product, amount, term, rate),
                        reasons=[Reason("OK", "Заявка соответствует условиям продукта")], **common)

    # Не хватает лимита: сначала пробуем удлинить срок, потом уменьшить сумму.
    for longer in (t for t in (12, 18, 24, 36, 48, 60, 84) if term < t <= product.max_term):
        lim = credit_limit(app, grade, product, longer, rate)
        if lim >= amount:
            return Decision(Outcome.COUNTER_OFFER, max_amount=lim,
                            offer=_make_offer(product, amount, longer, rate),
                            reasons=[Reason("CO_LONGER_TERM",
                                            f"Запрошенная сумма доступна на срок {longer} мес.: так ниже ежемесячный платёж")],
                            **common)

    if limit >= product.min_amount:
        return Decision(Outcome.COUNTER_OFFER, max_amount=limit, offer=_make_offer(product, limit, term, rate),
                        reasons=[Reason("CO_LOWER_AMOUNT",
                                        "Запрошенная сумма превышает платёжеспособность по оборотам; предложена меньшая")],
                        **common)

    return Decision(Outcome.DECLINED, max_amount=limit, offer=None,
                    reasons=[Reason("LOW_CAPACITY", "Оборотов недостаточно для обслуживания минимальной суммы продукта")],
                    **common)


def _make_offer(product: Product, amount: float, term: int, rate: float) -> Offer:
    amount = float(int(amount // 10_000) * 10_000)
    payment = float(annuity_payment(amount, rate / 100.0, term))
    return Offer(product.code, product.name, amount, term, rate, round(payment, 2))


class DecisionEngine:
    def __init__(self, model: ScoringModel):
        self.model = model

    def evaluate(self, app: dict) -> Decision:
        scored = None
        if not _stop_factors(app) and not _info_requests(app)[0]:
            scored = self.model.score(pd.DataFrame([app]))[0]
        return decide(app, scored, model_version=self.model.version)
