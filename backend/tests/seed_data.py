import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from application.decision_request import months_between
from domain.entities.enrichment_snapshot import EnrichmentSource
from domain.entities.loan_application import LoanApplication
from domain.products import LoanPurpose, ProductCode

SEED_FILE = Path(__file__).resolve().parents[2] / "seed" / "companies.json"


def seed_companies() -> list[dict[str, Any]]:
    companies: list[dict[str, Any]] = json.loads(SEED_FILE.read_text(encoding="utf-8"))[
        "companies"
    ]
    return companies


def seed_company(inn: str) -> dict[str, Any]:
    return next(c for c in seed_companies() if c["inn"] == inn)


def mock_payloads(company: dict[str, Any], today: date) -> dict[EnrichmentSource, Any]:
    sources = company["sources"]
    statement = dict(
        sources["statement"],
        bank_client_months=months_between(
            date.fromisoformat(company["bank_client_since"]), today
        ),
    )
    return {
        EnrichmentSource.EGRUL: sources["egrul"],
        EnrichmentSource.FNS: sources["fns"],
        EnrichmentSource.BKI: sources["bki"],
        EnrichmentSource.STATEMENT: statement,
    }


def demo_application(company: dict[str, Any]) -> LoanApplication:
    request = company["demo_request"]
    return LoanApplication.create_draft(
        company_id=UUID(company["id"]),
        created_by=uuid4(),
        actor_id=uuid4(),
        product=ProductCode(request["product"]),
        requested_amount=Decimal(str(request["requested_amount"])),
        term_months=request["term_months"],
        purpose=LoanPurpose(request["purpose"]),
        collateral_value=Decimal(str(request["collateral_value"])),
        collateral_description=None,
        at=datetime.now(UTC),
    )
