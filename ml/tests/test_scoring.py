from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from credit_scoring.decision import Outcome, decide, grade_for
from credit_scoring.features import MODEL_FEATURES, build_features
from credit_scoring.model import ScoreResult, ScoringModel, pd_to_score
from credit_scoring.service import app
from credit_scoring.synth import generate

ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"
needs_model = pytest.mark.skipif(not (ARTIFACTS / "model.txt").exists(), reason="модель не обучена")

GOOD = dict(
    legal_form="OOO", industry="services", region_tier=1, business_age_months=72, employees=25,
    annual_revenue=60_000_000, avg_monthly_turnover=4_500_000, turnover_volatility=0.15,
    turnover_trend_12m=0.15, net_margin=0.14, existing_debt=2_000_000, monthly_debt_payments=120_000,
    bki_history_months=60, max_overdue_days_12m=0, overdue_count_24m=0, credit_inquiries_3m=0,
    tax_arrears=0, mass_address=0, director_changes_12m=0, bank_client_months=48,
    cash_withdrawal_share=0.05, top_counterparty_share=0.2,
    product="express", requested_amount=3_000_000, term_months=24, collateral_value=0,
)


def test_synth_is_deterministic_and_plausible():
    a, b = generate(5000, seed=1), generate(5000, seed=1)
    pd.testing.assert_frame_equal(a, b)
    assert 0.03 < a.default_12m.mean() < 0.12


def test_features_shape_and_validation():
    X = build_features(pd.DataFrame([GOOD]))
    assert list(X.columns) == MODEL_FEATURES
    with pytest.raises(ValueError):
        build_features(pd.DataFrame([{**GOOD, "industry": "casino"}]))


def test_grades_and_score_monotone():
    assert [grade_for(p) for p in (0.01, 0.03, 0.05, 0.1, 0.2)] == list("ABCDE")
    assert pd_to_score(0.01) > pd_to_score(0.05) > pd_to_score(0.2)


def _scored(pd_value):
    return ScoreResult(pd=pd_value, score=pd_to_score(pd_value), risk_factors=[], positive_factors=[])


def test_policy_outcomes():
    assert decide(GOOD, _scored(0.015)).outcome == Outcome.APPROVED
    assert decide({**GOOD, "max_overdue_days_12m": 120}, None).outcome == Outcome.DECLINED
    assert decide({**GOOD, "tax_arrears": 1}, None).outcome == Outcome.REQUEST_INFO
    assert decide(GOOD, _scored(0.30)).outcome == Outcome.DECLINED
    small = {**GOOD, "avg_monthly_turnover": 1_500_000}
    longer = decide({**small, "requested_amount": 4_000_000, "term_months": 6}, _scored(0.015))
    assert longer.outcome == Outcome.COUNTER_OFFER and longer.offer.term_months > 6
    lower = decide({**small, "requested_amount": 9_000_000, "term_months": 36}, _scored(0.015))
    assert lower.outcome == Outcome.COUNTER_OFFER and lower.offer.amount < 9_000_000
    assert decide({**GOOD, "mass_address": 1}, _scored(0.015)).outcome == Outcome.MANUAL_REVIEW


def test_same_pd_different_products():
    # Один и тот же риск, но для инвестиционного кредита без залога нужен залог.
    inv = {**GOOD, "product": "investment", "requested_amount": 20_000_000, "term_months": 60}
    assert decide(inv, _scored(0.015)).outcome == Outcome.REQUEST_INFO
    assert decide({**inv, "collateral_value": 25_000_000}, _scored(0.015)).outcome in {
        Outcome.APPROVED, Outcome.COUNTER_OFFER}


@needs_model
def test_model_monotone_on_overdue_and_ranks_risk():
    m = ScoringModel(ARTIFACTS)
    base = pd.DataFrame([GOOD] * 4)
    base["max_overdue_days_12m"] = [0, 10, 45, 80]
    base["overdue_count_24m"] = [0, 1, 2, 3]
    pds = m.predict_pd(base)
    assert np.all(np.diff(pds) >= 0)

    df = generate(4000, seed=7)
    p = m.predict_pd(df)
    from sklearn.metrics import roc_auc_score
    assert roc_auc_score(df.default_12m, p) > 0.70


@needs_model
def test_api_decision():
    with TestClient(app) as c:
        assert c.get("/health").json()["status"] == "ok"
        r = c.post("/v1/decision", json={**GOOD, "tax_arrears": False, "mass_address": False})
        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] in {o.value for o in Outcome}
        assert body["pd"] is not None and body["offer"] is not None
        assert c.post("/v1/decision", json={**GOOD, "industry": "casino"}).status_code == 422
