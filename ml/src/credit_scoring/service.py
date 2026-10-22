"""HTTP-сервис скоринга и кредитного решения (FastAPI).

Бэкенд кредитного конвейера отправляет сюда заявку, уже обогащённую данными
из выписки, БКИ и ФНС (в прототипе — моки), и получает решение с объяснением.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Literal

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

from .decision import POLICY_VERSION, PRODUCTS, DecisionEngine, key_rate
from .model import ScoringModel


class ApplicationIn(BaseModel):
    """Заявка + данные обогащения. Все суммы в рублях."""

    application_id: str | None = None
    # Компания
    legal_form: Literal["IP", "OOO"]
    industry: Literal["trade", "services", "manufacturing", "construction",
                      "food_service", "transport", "it", "agriculture"]
    region_tier: int = Field(2, ge=1, le=3, description="1 — Москва/СПб, 2 — крупные города, 3 — прочие")
    business_age_months: int = Field(ge=0, le=1200)
    employees: int = Field(ge=0, le=10_000)
    # Финансы (выписка по счёту, отчётность)
    annual_revenue: float = Field(gt=0)
    avg_monthly_turnover: float = Field(ge=0)
    turnover_volatility: float = Field(ge=0, le=5, description="Коэффициент вариации месячных оборотов")
    turnover_trend_12m: float = Field(ge=-1, le=10, description="Рост оборотов год к году, доля")
    net_margin: float = Field(ge=-1, le=1)
    existing_debt: float = Field(0, ge=0)
    monthly_debt_payments: float = Field(0, ge=0)
    cash_withdrawal_share: float = Field(0, ge=0, le=1)
    top_counterparty_share: float = Field(0.3, ge=0, le=1)
    bank_client_months: int = Field(0, ge=0)
    # БКИ
    bki_history_months: int = Field(0, ge=0)
    max_overdue_days_12m: int = Field(0, ge=0)
    overdue_count_24m: int = Field(0, ge=0)
    credit_inquiries_3m: int = Field(0, ge=0)
    # ФНС / ЕГРЮЛ
    tax_arrears: bool = False
    mass_address: bool = False
    director_changes_12m: int = Field(0, ge=0)
    # Параметры заявки
    product: Literal["express", "overdraft", "investment"]
    requested_amount: float = Field(gt=0)
    term_months: int = Field(ge=1, le=120)
    collateral_value: float = Field(0, ge=0)

    def as_raw(self) -> dict:
        d = self.model_dump(exclude={"application_id"})
        d["tax_arrears"] = int(d["tax_arrears"])
        d["mass_address"] = int(d["mass_address"])
        return d


@asynccontextmanager
async def lifespan(_app):
    engine()  # прогреваем модель при старте, а не на первом запросе
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Credit Scoring Service",
    version="0.1.0",
    description="PD-скоринг МСБ и кредитная политика. Данные синтетические.",
)


@lru_cache(maxsize=1)
def engine() -> DecisionEngine:
    return DecisionEngine(ScoringModel())


@app.get("/health")
def health():
    return {"status": "ok", "model_version": engine().model.version}


@app.get("/v1/model")
def model_info():
    card = engine().model.card
    return {
        "model_version": card["model_version"],
        "policy_version": POLICY_VERSION,
        "key_rate": key_rate(),
        "algorithm": card["algorithm"],
        "target": card["target"],
        "metrics_oot": card["metrics"]["oot"],
        "stability": card["stability"],
        "grades_oot": card["grades_oot"],
        "limitations": card["limitations"],
    }


@app.get("/v1/products")
def products():
    return [p.__dict__ for p in PRODUCTS.values()]


@app.post("/v1/score")
def score(appl: ApplicationIn):
    """Только оценка риска: PD, балл и вклад факторов, без кредитного решения."""
    m = engine().model
    r = m.score(pd.DataFrame([appl.as_raw()]))[0]
    return {
        "application_id": appl.application_id,
        "pd": round(r.pd, 4),
        "score": r.score,
        "risk_factors": [f.__dict__ for f in r.risk_factors],
        "positive_factors": [f.__dict__ for f in r.positive_factors],
        "model_version": m.version,
    }


@app.post("/v1/decision")
def decision(appl: ApplicationIn):
    """Полное кредитное решение: исход, условия, причины, факторы риска."""
    d = engine().evaluate(appl.as_raw()).to_dict()
    d["application_id"] = appl.application_id
    return d
