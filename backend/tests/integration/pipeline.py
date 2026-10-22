from collections.abc import AsyncIterator, Callable
from datetime import date
from typing import Any
from uuid import UUID

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.use_cases.processing.disburse import Disburse
from application.use_cases.processing.process_application import (
    ProcessApplication,
    Sources,
)
from core.configs.services import MocksSettings, ScoringSettings
from domain.entities.enrichment_snapshot import EnrichmentSource
from domain.entities.user import UserRole
from infra.clock import SystemClock
from infra.http.scoring import HttpScoringGateway
from infra.http.sources import (
    HttpAbsGateway,
    HttpBkiGateway,
    HttpEgrulGateway,
    HttpFnsGateway,
)
from infra.postgres.uow import SqlAlchemyUnitOfWork
from tests.seed_data import mock_payloads, seed_company

ML = "http://ml.test"
MOCKS = "http://mocks.test"
Login = Callable[[UUID, UserRole], None]


def ml_response(outcome: str, **overrides: Any) -> dict[str, Any]:
    response = {
        "outcome": outcome,
        "pd": 0.0123,
        "score": 742,
        "grade": "A",
        "max_amount": 6450000.0,
        "offer": {
            "product": "express",
            "product_name": "Экспресс-кредит на оборотные средства",
            "amount": 1500000.0,
            "term_months": 12,
            "rate": 19.0,
            "monthly_payment": 138234.87,
        },
        "reasons": [{"code": "OK", "text": "Заявка соответствует условиям продукта"}],
        "risk_factors": [
            {
                "feature": "x",
                "label": "Высокая доля наличных",
                "value": 0.1,
                "impact": 0.2,
            }
        ],
        "positive_factors": [
            {
                "feature": "y",
                "label": "Длинная кредитная история",
                "value": 64,
                "impact": -0.4,
            }
        ],
        "requested_documents": [],
        "model_version": "pd-smb-lgbm-test",
        "policy_version": "policy-test",
        "application_id": None,
    }
    return response | overrides


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def process(
    sessionmaker: async_sessionmaker[AsyncSession], http_client: httpx.AsyncClient
) -> ProcessApplication:
    mocks = MocksSettings(URL=MOCKS, ATTEMPTS=1)
    return ProcessApplication(
        uow=SqlAlchemyUnitOfWork(sessionmaker),
        clock=SystemClock(),
        sources=Sources(
            egrul=HttpEgrulGateway(http_client, mocks),
            fns=HttpFnsGateway(http_client, mocks),
            bki=HttpBkiGateway(http_client, mocks),
            abs=HttpAbsGateway(http_client, mocks),
        ),
        scoring=HttpScoringGateway(http_client, ScoringSettings(URL=ML, ATTEMPTS=1)),
    )


def route_mocks(router: respx.MockRouter, inn: str) -> None:
    payloads = mock_payloads(seed_company(inn), date.today())
    router.get(f"{MOCKS}/egrul/{inn}").respond(json=payloads[EnrichmentSource.EGRUL])
    router.get(f"{MOCKS}/fns/{inn}/arrears").respond(
        json=payloads[EnrichmentSource.FNS]
    )
    router.get(f"{MOCKS}/bki/{inn}/report").respond(json=payloads[EnrichmentSource.BKI])
    router.get(f"{MOCKS}/abs/{inn}/statement").respond(
        json=payloads[EnrichmentSource.STATEMENT]
    )


async def submitted(client: httpx.AsyncClient, **draft: Any) -> str:
    body = {
        "product": "express",
        "requested_amount": 1500000,
        "term_months": 12,
        "purpose": "working_capital",
    } | draft
    card = (await client.post("/api/v1/applications", json=body)).json()
    await client.post(
        f"/api/v1/applications/{card['id']}/submit",
        json={"consent_bki": True, "consent_pd": True},
    )
    return str(card["id"])


@pytest.fixture
def disburse(
    sessionmaker: async_sessionmaker[AsyncSession], http_client: httpx.AsyncClient
) -> Disburse:
    return Disburse(
        uow=SqlAlchemyUnitOfWork(sessionmaker),
        clock=SystemClock(),
        abs_gateway=HttpAbsGateway(http_client, MocksSettings(URL=MOCKS, ATTEMPTS=1)),
    )


async def scored(
    client: httpx.AsyncClient,
    process: ProcessApplication,
    inn: str,
    response: dict[str, Any],
    **draft: Any,
) -> str:
    application_id = await submitted(client, **draft)
    with respx.mock() as router:
        route_mocks(router, inn)
        router.post(f"{ML}/v1/decision").respond(json=response)
        await process(UUID(application_id))
    return application_id
