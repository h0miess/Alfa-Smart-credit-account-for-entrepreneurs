"""Генератор синтетических заявок МСБ с исходом «дефолт за 12 месяцев».

Реальных данных у нас нет (и не будет), поэтому дефолт генерируется из
явно заданного «истинного» процесса риска: экспертные эффекты факторов
+ скрытый финансовый стресс компании, который частично виден через
наблюдаемые признаки. Модель должна восстановить эту зависимость по
наблюдаемым данным, не видя скрытой переменной.

Целевая доля дефолтов ~6-8%, что близко к рыночному уровню риска в МСБ.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .features import INDUSTRIES, annuity_payment

# Отраслевой риск (лог-шансы) и параметры отраслей.
INDUSTRY_PROFILE = {
    #               доля  риск  маржа  сезонность
    "trade":         (0.30, 0.00, 0.06, 0.15),
    "services":      (0.20, -0.10, 0.12, 0.10),
    "manufacturing": (0.10, -0.15, 0.09, 0.10),
    "construction":  (0.10, 0.45, 0.07, 0.30),
    "food_service":  (0.10, 0.40, 0.05, 0.20),
    "transport":     (0.08, 0.20, 0.07, 0.15),
    "it":            (0.07, -0.30, 0.18, 0.05),
    "agriculture":   (0.05, 0.25, 0.08, 0.40),
}
assert list(INDUSTRY_PROFILE) == INDUSTRIES


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def generate(n: int = 60_000, seed: int = 42, with_truth: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # Дата заявки: 2023-01 .. 2026-06. Нужна для out-of-time проверки.
    month_idx = rng.integers(0, 42, n)
    app_month = pd.period_range("2023-01", periods=42, freq="M")[month_idx].astype(str)

    legal_form = np.where(rng.random(n) < 0.6, "IP", "OOO")
    is_ooo = legal_form == "OOO"

    probs = np.array([p[0] for p in INDUSTRY_PROFILE.values()])
    industry = rng.choice(INDUSTRIES, n, p=probs / probs.sum())
    ind_risk = np.array([INDUSTRY_PROFILE[i][1] for i in industry])
    ind_margin = np.array([INDUSTRY_PROFILE[i][2] for i in industry])
    ind_season = np.array([INDUSTRY_PROFILE[i][3] for i in industry])

    region_tier = rng.choice([1, 2, 3], n, p=[0.35, 0.45, 0.20])

    # Скрытый финансовый стресс: модель его не видит напрямую.
    stress = rng.normal(0, 1, n)

    business_age = np.exp(rng.normal(np.where(is_ooo, 4.0, 3.5), 0.9, n))
    business_age = np.clip(business_age, 2, 360).round()

    employees = np.where(
        is_ooo,
        np.exp(rng.normal(2.3, 1.0, n)),
        rng.poisson(2.0, n),
    )
    employees = np.clip(employees, 0, 250).round()

    # Выручка, руб./год. Верхняя граница — порог малого бизнеса (800 млн).
    log_rev = (
        np.where(is_ooo, 17.4, 15.6)
        + 0.35 * np.log1p(employees)
        + 0.15 * np.log(business_age / 24)
        + rng.normal(0, 0.7, n)
    )
    annual_revenue = np.clip(np.exp(log_rev), 3e5, 8e8).round(-3)

    bank_share = np.clip(rng.beta(5, 2, n), 0.15, 1.0)
    avg_monthly_turnover = (annual_revenue / 12 * bank_share).round(-2)

    turnover_volatility = np.clip(
        ind_season + rng.gamma(2.0, 0.07, n) + 0.06 * np.maximum(stress, 0), 0.03, 1.2
    )
    turnover_trend = np.clip(rng.normal(0.08, 0.22, n) - 0.10 * stress, -0.8, 1.5)
    net_margin = np.clip(ind_margin + rng.normal(0, 0.06, n) - 0.025 * stress, -0.3, 0.45)

    has_debt = rng.random(n) < np.clip(0.45 + 0.1 * stress, 0.05, 0.95)
    existing_debt = np.where(
        has_debt, annual_revenue * np.exp(rng.normal(-1.6 + 0.25 * stress, 0.6, n)), 0.0
    ).round(-3)
    monthly_debt_payments = (existing_debt / rng.uniform(12, 36, n) * 1.12).round(-2)

    # БКИ. Часть клиентов без кредитной истории.
    bki_history = np.where(
        has_debt | (rng.random(n) < 0.4),
        np.minimum(business_age, rng.exponential(40, n)),
        0,
    ).round()
    has_hist = bki_history > 0
    od_lambda = np.exp(-2.6 + 0.85 * stress)
    overdue_count_24m = np.where(has_hist, rng.poisson(od_lambda), 0)
    worst = rng.choice(
        [5, 15, 45, 75, 120],
        n,
        p=[0.45, 0.25, 0.15, 0.10, 0.05],
    ) * np.exp(rng.normal(0.25 * stress, 0.4, n))
    max_overdue_12m = np.where(
        (overdue_count_24m > 0) & (rng.random(n) < 0.7), np.clip(worst, 1, 365), 0
    ).round()
    credit_inquiries_3m = rng.poisson(np.exp(0.0 + 0.35 * stress))

    tax_arrears = (rng.random(n) < _sigmoid(-3.4 + 0.7 * stress)).astype(int)
    mass_address = ((rng.random(n) < 0.05) & is_ooo).astype(int)
    director_changes = np.where(is_ooo, rng.poisson(0.12 + 0.05 * np.maximum(stress, 0)), 0)

    bank_client_months = np.minimum(business_age, rng.exponential(30, n)).round()
    cash_withdrawal_share = np.clip(rng.beta(1.5, 8, n) + 0.04 * np.maximum(stress, 0), 0, 1)
    top_counterparty_share = np.clip(rng.beta(2, 4, n), 0.02, 1.0)

    # Параметры заявки.
    product = rng.choice(["express", "overdraft", "investment"], n, p=[0.5, 0.3, 0.2])
    term = np.select(
        [product == "express", product == "overdraft"],
        [rng.choice([6, 12, 18, 24, 36], n), np.full(n, 12)],
        rng.choice([24, 36, 48, 60, 84], n),
    )
    amount = np.select(
        [product == "express", product == "overdraft"],
        [
            avg_monthly_turnover * np.exp(rng.normal(0.4 + 0.15 * stress, 0.7, n)),
            avg_monthly_turnover * rng.uniform(0.2, 0.9, n),
        ],
        annual_revenue * np.exp(rng.normal(-1.0, 0.6, n)),
    )
    amount = np.select(
        [product == "express", product == "overdraft"],
        [np.clip(amount, 1e5, 1e7), np.clip(amount, 5e4, 1.5e7)],
        np.clip(amount, 1e6, 1e8),
    ).round(-4)

    has_collateral = np.where(
        product == "investment", rng.random(n) < 0.75, rng.random(n) < 0.08
    )
    collateral_value = np.where(has_collateral, amount * rng.uniform(0.6, 1.8, n), 0.0).round(-4)

    # «Истинный» процесс дефолта.
    new_payment = annuity_payment(amount, 0.22, term)
    dsr = (monthly_debt_payments + new_payment) / np.maximum(avg_monthly_turnover, 1)
    dtr = (existing_debt + amount) / annual_revenue
    coll_cov = np.minimum(collateral_value / amount, 3)

    logit = (
        -4.05
        + ind_risk
        + 0.10 * (region_tier - 2)
        - 0.45 * np.log(np.clip(business_age, 3, 120) / 24)
        + 3.0 * np.clip(dsr - 0.25, 0, 1.0)
        + 0.6 * np.clip(dtr - 0.5, 0, 2)
        + 1.0 * turnover_volatility
        - 0.9 * np.clip(turnover_trend, -0.6, 0.6)
        - 2.5 * net_margin
        + 0.45 * np.minimum(overdue_count_24m, 4)
        + np.select(
            [max_overdue_12m > 90, max_overdue_12m > 30, max_overdue_12m > 0],
            [1.8, 0.9, 0.25],
            0.0,
        )
        + 0.18 * np.minimum(credit_inquiries_3m, 6)
        + 0.9 * tax_arrears
        + 0.7 * mass_address
        + 0.3 * director_changes
        - 0.18 * np.log1p(bank_client_months / 6)
        + 1.2 * cash_withdrawal_share
        + 0.6 * top_counterparty_share
        + 0.35 * (~has_hist)
        - 0.45 * np.clip(coll_cov, 0, 1.2)
        + 0.6 * stress
        # Лёгкий дрейф во времени: в поздних когортах риск чуть выше.
        + 0.004 * month_idx
    )
    pd_true = _sigmoid(logit)
    default_12m = (rng.random(n) < pd_true).astype(int)

    df = pd.DataFrame(
        {
            "application_id": [f"SYN-{i:06d}" for i in range(n)],
            "application_month": app_month,
            "legal_form": legal_form,
            "industry": industry,
            "product": product,
            "region_tier": region_tier,
            "business_age_months": business_age,
            "employees": employees,
            "annual_revenue": annual_revenue,
            "avg_monthly_turnover": avg_monthly_turnover,
            "turnover_volatility": turnover_volatility.round(3),
            "turnover_trend_12m": turnover_trend.round(3),
            "net_margin": net_margin.round(3),
            "existing_debt": existing_debt,
            "monthly_debt_payments": monthly_debt_payments,
            "bki_history_months": bki_history,
            "max_overdue_days_12m": max_overdue_12m,
            "overdue_count_24m": overdue_count_24m,
            "credit_inquiries_3m": credit_inquiries_3m,
            "tax_arrears": tax_arrears,
            "mass_address": mass_address,
            "director_changes_12m": director_changes,
            "bank_client_months": bank_client_months,
            "cash_withdrawal_share": cash_withdrawal_share.round(3),
            "top_counterparty_share": top_counterparty_share.round(3),
            "requested_amount": amount,
            "term_months": term,
            "collateral_value": collateral_value,
            "default_12m": default_12m,
        }
    )
    if with_truth:
        # Только для оценки потолка качества; в обучение не идёт.
        df["_pd_true"] = pd_true
    return df


def main():
    ap = argparse.ArgumentParser(description="Сгенерировать синтетический датасет заявок")
    ap.add_argument("--n", type=int, default=150_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path("data/applications.csv"))
    args = ap.parse_args()

    df = generate(args.n, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"{len(df)} заявок -> {args.out}, доля дефолтов {df.default_12m.mean():.3%}")


if __name__ == "__main__":
    main()
