"""Единое описание признаков: используется и при обучении, и в сервисе.

Сырые поля приходят из заявки и обогащения (выписка по счёту, БКИ, ФНС/ЕГРЮЛ).
Производные признаки считаются здесь же, чтобы обучение и прод-инференс
гарантированно видели одно и то же.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Справочная ставка только для расчёта нагрузки в признаках. Реальная ставка
# зависит от решения, а признаки от решения зависеть не должны.
REFERENCE_RATE = 0.22

LEGAL_FORMS = ["IP", "OOO"]
INDUSTRIES = [
    "trade",
    "services",
    "manufacturing",
    "construction",
    "food_service",
    "transport",
    "it",
    "agriculture",
]
PRODUCTS = ["express", "overdraft", "investment"]

CATEGORICAL = {
    "legal_form": LEGAL_FORMS,
    "industry": INDUSTRIES,
    "product": PRODUCTS,
}

RAW_NUMERIC = [
    "region_tier",
    "business_age_months",
    "employees",
    "annual_revenue",
    "avg_monthly_turnover",
    "turnover_volatility",
    "turnover_trend_12m",
    "net_margin",
    "existing_debt",
    "monthly_debt_payments",
    "bki_history_months",
    "max_overdue_days_12m",
    "overdue_count_24m",
    "credit_inquiries_3m",
    "tax_arrears",
    "mass_address",
    "director_changes_12m",
    "bank_client_months",
    "cash_withdrawal_share",
    "top_counterparty_share",
    "requested_amount",
    "term_months",
    "collateral_value",
]

RAW_FIELDS = list(CATEGORICAL) + RAW_NUMERIC

DERIVED = [
    "log_revenue",
    "new_payment_ref",
    "debt_service_ratio",
    "debt_to_revenue",
    "amount_to_turnover",
    "collateral_coverage",
    "bank_turnover_share",
]

# Что идёт в модель. Сырые суммы в рублях заменены относительными показателями,
# чтобы модель не училась на масштабе бизнеса.
MODEL_FEATURES = [
    "legal_form",
    "industry",
    "product",
    "region_tier",
    "business_age_months",
    "employees",
    "log_revenue",
    "turnover_volatility",
    "turnover_trend_12m",
    "net_margin",
    "debt_service_ratio",
    "debt_to_revenue",
    "amount_to_turnover",
    "collateral_coverage",
    "bank_turnover_share",
    "bki_history_months",
    "max_overdue_days_12m",
    "overdue_count_24m",
    "credit_inquiries_3m",
    "tax_arrears",
    "mass_address",
    "director_changes_12m",
    "bank_client_months",
    "cash_withdrawal_share",
    "top_counterparty_share",
    "term_months",
]

# Направление влияния на риск (+1 растёт, -1 падает, 0 без ограничения).
# Монотонность делает модель объяснимой и защищает от абсурдных выводов
# вроде «больше просрочек — меньше риск».
MONOTONE = {
    "business_age_months": -1,
    "turnover_volatility": +1,
    "turnover_trend_12m": -1,
    "net_margin": -1,
    "debt_service_ratio": +1,
    "debt_to_revenue": +1,
    "amount_to_turnover": +1,
    "collateral_coverage": -1,
    "max_overdue_days_12m": +1,
    "overdue_count_24m": +1,
    "credit_inquiries_3m": +1,
    "tax_arrears": +1,
    "mass_address": +1,
    "director_changes_12m": +1,
    "bank_client_months": -1,
    "cash_withdrawal_share": +1,
    "top_counterparty_share": +1,
}

# Человекочитаемые названия для объяснений клиенту и андеррайтеру.
FEATURE_LABELS = {
    "legal_form": "Организационно-правовая форма",
    "industry": "Отрасль",
    "product": "Кредитный продукт",
    "region_tier": "Регион",
    "business_age_months": "Срок работы бизнеса",
    "employees": "Численность сотрудников",
    "log_revenue": "Масштаб выручки",
    "turnover_volatility": "Стабильность оборотов по счёту",
    "turnover_trend_12m": "Динамика оборотов за 12 месяцев",
    "net_margin": "Рентабельность",
    "debt_service_ratio": "Платёжная нагрузка с учётом нового кредита",
    "debt_to_revenue": "Долговая нагрузка к выручке",
    "amount_to_turnover": "Запрошенная сумма к оборотам",
    "collateral_coverage": "Обеспечение (залог)",
    "bank_turnover_share": "Доля оборотов, проходящих через банк",
    "bki_history_months": "Длина кредитной истории",
    "max_overdue_days_12m": "Просрочки за 12 месяцев",
    "overdue_count_24m": "Количество просрочек за 24 месяца",
    "credit_inquiries_3m": "Запросы в БКИ за 3 месяца",
    "tax_arrears": "Задолженность по налогам",
    "mass_address": "Адрес массовой регистрации",
    "director_changes_12m": "Смены руководителя за 12 месяцев",
    "bank_client_months": "Срок обслуживания в банке",
    "cash_withdrawal_share": "Доля снятия наличных",
    "top_counterparty_share": "Зависимость от одного контрагента",
    "term_months": "Срок кредита",
}


def annuity_payment(principal, annual_rate, term_months):
    """Аннуитетный платёж. Работает и со скалярами, и с массивами."""
    r = np.asarray(annual_rate, dtype=float) / 12.0
    n = np.maximum(np.asarray(term_months, dtype=float), 1.0)
    p = np.asarray(principal, dtype=float)
    return p * r / (1.0 - (1.0 + r) ** (-n))


def max_principal_for_payment(payment, annual_rate, term_months):
    """Обратная задача: какую сумму можно выдать при заданном платеже."""
    r = annual_rate / 12.0
    n = max(float(term_months), 1.0)
    return payment * (1.0 - (1.0 + r) ** (-n)) / r


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Сырые поля -> матрица признаков модели (в порядке MODEL_FEATURES)."""
    missing = [c for c in RAW_FIELDS if c not in raw.columns]
    if missing:
        raise ValueError(f"Нет обязательных полей: {missing}")

    df = raw[RAW_FIELDS].copy()
    for col in RAW_NUMERIC:
        df[col] = pd.to_numeric(df[col]).astype(float)

    turnover = df["avg_monthly_turnover"].clip(lower=1.0)
    revenue = df["annual_revenue"].clip(lower=1.0)
    amount = df["requested_amount"].clip(lower=1.0)

    df["log_revenue"] = np.log10(revenue)
    df["new_payment_ref"] = annuity_payment(amount, REFERENCE_RATE, df["term_months"])
    df["debt_service_ratio"] = (df["monthly_debt_payments"] + df["new_payment_ref"]) / turnover
    df["debt_to_revenue"] = (df["existing_debt"] + amount) / revenue
    df["amount_to_turnover"] = amount / turnover
    df["collateral_coverage"] = (df["collateral_value"] / amount).clip(upper=3.0)
    df["bank_turnover_share"] = (turnover * 12.0 / revenue).clip(upper=1.5)

    for col, cats in CATEGORICAL.items():
        df[col] = pd.Categorical(df[col], categories=cats)
        if df[col].isna().any():
            raise ValueError(f"Неизвестное значение в поле {col}; допустимо: {cats}")

    return df[MODEL_FEATURES]


def monotone_vector() -> list[int]:
    return [MONOTONE.get(f, 0) for f in MODEL_FEATURES]
