from datetime import timedelta
from uuid import UUID

import httpx
import respx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.use_cases.processing.disburse import Disburse
from application.use_cases.processing.process_application import ProcessApplication
from domain.entities.user import UserRole
from infra.postgres.models import contract_table, offer_table
from infra.postgres.uow import SqlAlchemyUnitOfWork
from tests.fakes import FakeTaskQueue
from tests.integration.pipeline import MOCKS, Login, ml_response, scored
from tests.users import IP_IVANOV, ROMASHKA_ACCOUNTANT, ROMASHKA_DIRECTOR

IVANOV_INN = "772814539067"
ROMASHKA_INN = "7701846322"


def url(application_id: str, path: str = "") -> str:
    return f"/api/v1/applications/{application_id}{path}"


async def test_happy_path_to_issued(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
    disburse: Disburse,
    task_queue: FakeTaskQueue,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    app_id = await scored(client, process, IVANOV_INN, ml_response("APPROVED"))

    accepted = (await client.post(url(app_id, "/offer/accept"))).json()
    contract = (await client.get(url(app_id, "/contract"))).json()
    document = await client.get(url(app_id, "/contract/document"))
    code = (await client.post(url(app_id, "/contract/sign-code"))).json()
    wrong = "000000" if code["code"] != "000000" else "111111"
    rejected_sign = await client.post(
        url(app_id, "/contract/sign"), json={"code": wrong}
    )
    signed = await client.post(
        url(app_id, "/contract/sign"), json={"code": code["code"]}
    )

    assert accepted["status"]["code"] == "ACCEPTED"
    offer = accepted["offer"]
    assert (contract["amount"], contract["term_months"], contract["rate"]) == (
        offer["amount"],
        offer["term_months"],
        offer["rate"],
    )
    assert contract["monthly_payment"] == offer["monthly_payment"]
    assert contract["matches_offer"] is True
    assert "Подключение других продуктов банка не требуется" in document.text
    assert rejected_sign.status_code == 422
    assert signed.json()["status"]["code"] == "SIGNED"
    assert task_queue.disbursements == [UUID(app_id)]

    with respx.mock(assert_all_called=True) as router:
        abs_call = router.post(f"{MOCKS}/abs/disbursements").respond(
            201,
            json={
                "operation_id": "ABS-1",
                "account": "40802810400000012345",
                "amount": offer["amount"],
                "status": "COMPLETED",
            },
        )
        await disburse(UUID(app_id))
        await disburse(UUID(app_id))

    assert abs_call.call_count == 1
    assert abs_call.calls[0].request.headers["Idempotency-Key"] == contract["id"]
    card = (await client.get(url(app_id))).json()
    assert card["status"]["code"] == "ISSUED"
    assert card["status"]["title"] == "Деньги на счёте"
    assert [e["to_status"] for e in card["events"]] == [
        "DRAFT",
        "SUBMITTED",
        "CHECKING",
        "OFFERED",
        "ACCEPTED",
        "SIGNED",
        "ISSUED",
    ]
    async with SqlAlchemyUnitOfWork(sessionmaker) as uow:
        disbursement = await uow.disbursements.get_by_contract(UUID(contract["id"]))
    assert disbursement is not None
    assert disbursement.external_id == "ABS-1"


async def test_accountant_prepares_but_cannot_sign(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
) -> None:
    login(ROMASHKA_ACCOUNTANT, UserRole.CLIENT)
    response = ml_response(
        "COUNTER_OFFER",
        offer=ml_response("APPROVED")["offer"] | {"amount": 7190000.0},
    )
    app_id = await scored(
        client, process, ROMASHKA_INN, response, requested_amount=9000000
    )

    card = (await client.get(url(app_id))).json()
    assert card["offer"]["is_counter_offer"] is True
    assert card["offer"]["requested_amount"] == 9000000
    await client.post(url(app_id, "/offer/accept"))
    forbidden = await client.post(url(app_id, "/contract/sign-code"))

    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "signer_required"
    assert "руководитель" in forbidden.json()["details"]

    login(ROMASHKA_DIRECTOR, UserRole.CLIENT)
    assert (await client.post(url(app_id, "/contract/sign-code"))).status_code == 200


async def test_reject_offer_cancels_and_allows_new_application(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    app_id = await scored(client, process, IVANOV_INN, ml_response("APPROVED"))

    rejected = (await client.post(url(app_id, "/offer/reject"))).json()
    copy = await client.post(url(app_id, "/copy"))

    assert rejected["status"]["code"] == "CANCELLED"
    assert rejected["offer"]["status"] == "rejected"
    assert copy.status_code == 201


async def test_expired_offer_cannot_be_accepted(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    app_id = await scored(client, process, IVANOV_INN, ml_response("APPROVED"))
    card = (await client.get(url(app_id))).json()
    async with sessionmaker() as session:
        await session.execute(
            update(offer_table)
            .where(offer_table.c.id == card["offer"]["id"])
            .values(valid_until=offer_table.c.valid_until - timedelta(days=30))
        )
        await session.commit()

    response = await client.post(url(app_id, "/offer/accept"))

    assert response.status_code == 409
    assert response.json()["code"] == "offer_expired"
    card = (await client.get(url(app_id))).json()
    assert card["status"]["code"] == "CANCELLED"
    assert card["offer"]["status"] == "expired"


async def test_contract_differing_from_offer_is_not_signed(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    app_id = await scored(client, process, IVANOV_INN, ml_response("APPROVED"))
    await client.post(url(app_id, "/offer/accept"))
    code = (await client.post(url(app_id, "/contract/sign-code"))).json()["code"]
    async with sessionmaker() as session:
        await session.execute(update(contract_table).values(rate=25))
        await session.commit()

    response = await client.post(url(app_id, "/contract/sign"), json={"code": code})

    assert response.status_code == 409
    assert response.json()["code"] == "contract_mismatch"
