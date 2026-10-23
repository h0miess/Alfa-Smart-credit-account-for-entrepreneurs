from uuid import UUID

import httpx
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.use_cases.processing.process_application import (
    ProcessApplication,
    RetryPolicy,
)
from domain.entities.enrichment_snapshot import EnrichmentSource
from domain.entities.user import UserRole
from infra.postgres.uow import SqlAlchemyUnitOfWork
from tests.integration.pipeline import (
    ML,
    MOCKS,
    Login,
    build_process,
    ml_response,
    route_mocks,
    submitted,
)
from tests.users import IP_IVANOV, VECTOR_DIRECTOR


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


async def test_source_failure_keeps_checking_while_retrying(
    client: httpx.AsyncClient,
    login: Login,
    sessionmaker: async_sessionmaker[AsyncSession],
    http_client: httpx.AsyncClient,
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    application_id = await submitted(client)
    seen_while_waiting: list[str] = []

    async def check_status(_: float) -> None:
        card = (await client.get(f"/api/v1/applications/{application_id}")).json()
        seen_while_waiting.append(card["status"]["code"])

    process = build_process(
        sessionmaker,
        http_client,
        retry=RetryPolicy(attempts=2, first_delay_in_seconds=0),
        sleep=check_status,
    )
    with respx.mock() as router:
        route_mocks(router, "772814539067")
        router.get(f"{MOCKS}/bki/772814539067/report").respond(503)
        await process(UUID(application_id))

    assert seen_while_waiting == ["CHECKING"]
    card = (await client.get(f"/api/v1/applications/{application_id}")).json()
    assert card["status"]["code"] == "MANUAL_REVIEW"
