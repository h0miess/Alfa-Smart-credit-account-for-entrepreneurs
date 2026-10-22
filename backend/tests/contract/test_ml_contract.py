import os
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from application.decision_request import build_decision_request
from domain.outcomes import Grade
from domain.pricing import annuity_payment, rate_for
from infra.http.scoring import DecisionRequestIn
from seed.loader import build_company
from tests.seed_data import demo_application, mock_payloads, seed_companies

ML_URL = os.environ.get("ML_URL")

pytestmark = [
    pytest.mark.contract,
    pytest.mark.skipif(not ML_URL, reason="нужен запущенный ml: ML_URL"),
]


def ml_get(path: str) -> Any:
    return httpx.get(f"{ML_URL}{path}", timeout=10).json()


def test_request_mirror_matches_ml_schema() -> None:
    schema = ml_get("/openapi.json")["components"]["schemas"]["ApplicationIn"]
    mirror = DecisionRequestIn.model_json_schema()

    assert set(mirror["properties"]) == set(schema["properties"])
    assert set(mirror.get("required", [])) == set(schema.get("required", []))


@pytest.mark.parametrize("company", seed_companies(), ids=lambda c: c["name"])
def test_seed_profile_gives_declared_outcome(company: dict[str, Any]) -> None:
    today = date.today()
    request = build_decision_request(
        demo_application(company),
        build_company(company),
        mock_payloads(company, today),
        [],
        today,
    )
    payload = DecisionRequestIn.model_validate(request).model_dump(mode="json")

    decision = httpx.post(f"{ML_URL}/v1/decision", json=payload, timeout=10).json()

    assert decision["outcome"] == company["expected_outcome"]
    if decision["offer"]:
        products = {p["code"]: p for p in ml_get("/v1/products")}
        key_rate = Decimal(str(ml_get("/v1/model")["key_rate"]))
        offer = decision["offer"]
        coverage = Decimal(str(payload["collateral_value"])) / Decimal(
            str(payload["requested_amount"])
        )
        expected_rate = rate_for(
            key_rate,
            Grade(decision["grade"]),
            Decimal(str(products[offer["product"]]["rate_adj"])),
            coverage,
        )
        assert Decimal(str(offer["rate"])) == expected_rate
        assert annuity_payment(
            Decimal(str(offer["amount"])), expected_rate, offer["term_months"]
        ) == Decimal(str(offer["monthly_payment"]))
