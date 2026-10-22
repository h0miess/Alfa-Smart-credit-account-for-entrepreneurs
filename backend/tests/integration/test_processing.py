from collections.abc import AsyncIterator, Callable
from datetime import date
from typing import Any
from uuid import UUID

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
from tests.users import IP_IVANOV, VECTOR_DIRECTOR

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


async def test_approved_application_gets_offer_decision_and_snapshots(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    application_id = await submitted(client)

    with respx.mock(assert_all_called=True) as router:
        route_mocks(router, "772814539067")
        decision_call = router.post(f"{ML}/v1/decision").respond(
            json=ml_response("APPROVED")
        )
        await process(UUID(application_id))
        await process(UUID(application_id))

    assert decision_call.call_count == 1
    sent = decision_call.calls[0].request
    assert b'"tax_arrears":false' in sent.content.replace(b" ", b"")

    card = (await client.get(f"/api/v1/applications/{application_id}")).json()
    assert card["status"]["code"] == "OFFERED"
    assert [e["to_status"] for e in card["events"]] == [
        "DRAFT",
        "SUBMITTED",
        "CHECKING",
        "OFFERED",
    ]
    assert card["offer"]["amount"] == 1500000
    assert card["offer"]["monthly_payment"] == 138234.87
    assert card["offer"]["note"] == "Подключение других продуктов банка не требуется"
    assert card["decision"]["risk_factors"] == ["Высокая доля наличных"]
    assert "pd" not in card["decision"]

    async with SqlAlchemyUnitOfWork(sessionmaker) as uow:
        decision = await uow.decisions.latest_for_application(UUID(application_id))
        assert decision is not None
        snapshots = await uow.snapshots.list_for_decision(decision.id)
    assert decision.model_version == "pd-smb-lgbm-test"
    assert decision.policy_version == "policy-test"
    assert decision.raw_response == ml_response("APPROVED")
    assert decision.request_payload is not None
    assert decision.request_payload["application_id"] == application_id
    assert {s.source for s in snapshots} == set(EnrichmentSource)


async def test_request_info_lists_documents(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
) -> None:
    login(VECTOR_DIRECTOR, UserRole.CLIENT)
    application_id = await submitted(client, requested_amount=3000000)

    with respx.mock() as router:
        route_mocks(router, "5406723981")
        router.post(f"{ML}/v1/decision").respond(
            json=ml_response(
                "REQUEST_INFO",
                pd=None,
                score=None,
                grade=None,
                max_amount=None,
                offer=None,
                reasons=[
                    {
                        "code": "INFO_TAX_ARREARS",
                        "text": "По данным ФНС есть задолженность по налогам",
                    }
                ],
                requested_documents=["Справка ФНС"],
            )
        )
        await process(UUID(application_id))

    card = (await client.get(f"/api/v1/applications/{application_id}")).json()
    assert card["status"]["code"] == "INFO_REQUESTED"
    assert card["offer"] is None
    assert card["requested_documents"] == [
        {
            "reason_code": "INFO_TAX_ARREARS",
            "kind": "tax_certificate",
            "title": "Справка ФНС об исполнении обязанности по уплате налогов "
            "или подтверждение погашения",
            "uploaded": False,
        }
    ]


async def test_source_failure_keeps_application_checking(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    application_id = await submitted(client)

    with respx.mock() as router:
        route_mocks(router, "772814539067")
        router.get(f"{MOCKS}/bki/772814539067/report").respond(503)
        with pytest.raises(Exception, match="БКИ"):
            await process(UUID(application_id))

    card = (await client.get(f"/api/v1/applications/{application_id}")).json()
    assert card["status"]["code"] == "CHECKING"
    assert card["decision"] is None
