import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import respx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.use_cases.processing.maintenance import (
    ExpireInfoRequests,
    ExpireOffers,
    RequeueStuck,
)
from application.use_cases.processing.process_application import (
    ProcessApplication,
    RetryPolicy,
)
from domain.entities.user import UserRole
from infra.clock import SystemClock
from infra.postgres.models import application_table, offer_table
from infra.postgres.uow import SqlAlchemyUnitOfWork
from tests.fakes import FakeTaskQueue
from tests.integration.pipeline import (
    ML,
    Login,
    build_process,
    ml_response,
    route_mocks,
    scored,
    submitted,
)
from tests.users import IP_IVANOV, UNDERWRITER

IVANOV_INN = "772814539067"


async def shift(
    sessionmaker: async_sessionmaker[AsyncSession], table: object, **values: object
) -> None:
    async with sessionmaker() as session:
        await session.execute(update(table).values(**values))  # type: ignore[arg-type]
        await session.commit()


async def test_failures_hand_application_to_underwriter(
    client: httpx.AsyncClient,
    login: Login,
    sessionmaker: async_sessionmaker[AsyncSession],
    http_client: httpx.AsyncClient,
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    application_id = await submitted(client)
    sleeps: list[float] = []

    async def no_wait(delay: float) -> None:
        sleeps.append(delay)

    retrying = build_process(
        sessionmaker,
        http_client,
        retry=RetryPolicy(attempts=3, first_delay_in_seconds=1),
        sleep=no_wait,
    )
    with respx.mock() as router:
        route_mocks(router, IVANOV_INN)
        ml = router.post(f"{ML}/v1/decision").respond(503)
        await retrying(UUID(application_id))

    assert ml.call_count == 3
    assert sleeps == [1, 2]
    card = (await client.get(f"/api/v1/applications/{application_id}")).json()
    assert card["status"]["code"] == "MANUAL_REVIEW"
    assert card["decision"]["reasons"][0]["code"] == "SYSTEM_UNAVAILABLE"

    login(UNDERWRITER, UserRole.UNDERWRITER)
    decided = await client.post(
        f"/api/v1/underwriter/applications/{application_id}/decision",
        json={
            "action": "change_terms",
            "amount": 1500000,
            "term_months": 12,
            "comment": "Проверил вручную по выписке",
        },
    )
    assert decided.status_code == 200
    login(IP_IVANOV, UserRole.CLIENT)
    card = (await client.get(f"/api/v1/applications/{application_id}")).json()
    assert card["status"]["code"] == "OFFERED"
    assert card["offer"]["rate"] == 26.0


async def test_expired_offer_is_cancelled_by_scheduler(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    application_id = await scored(client, process, IVANOV_INN, ml_response("APPROVED"))
    expire = ExpireOffers(SqlAlchemyUnitOfWork(sessionmaker), SystemClock())

    assert await expire() == 0
    await shift(
        sessionmaker,
        offer_table,
        valid_until=offer_table.c.valid_until - timedelta(days=15),
    )
    assert await expire() == 1
    assert await expire() == 0

    card = (await client.get(f"/api/v1/applications/{application_id}")).json()
    assert card["status"]["code"] == "CANCELLED"
    assert card["offer"]["status"] == "expired"


async def test_accept_racing_expiry_has_single_winner(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    application_id = await scored(client, process, IVANOV_INN, ml_response("APPROVED"))
    await shift(
        sessionmaker,
        offer_table,
        valid_until=offer_table.c.valid_until - timedelta(days=15),
    )
    expire = ExpireOffers(SqlAlchemyUnitOfWork(sessionmaker), SystemClock())

    accepted, expired = await asyncio.gather(
        client.post(f"/api/v1/applications/{application_id}/offer/accept"),
        expire(),
    )

    assert accepted.status_code == 409
    card = (await client.get(f"/api/v1/applications/{application_id}")).json()
    assert card["status"]["code"] == "CANCELLED"
    assert [e["to_status"] for e in card["events"]].count("CANCELLED") == 1
    assert expired in (0, 1)


async def test_info_request_without_answer_is_cancelled_after_30_days(
    client: httpx.AsyncClient,
    login: Login,
    process: ProcessApplication,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    application_id = await scored(
        client,
        process,
        IVANOV_INN,
        ml_response(
            "REQUEST_INFO",
            offer=None,
            reasons=[{"code": "INFO_LOW_TURNOVER", "text": "Малая доля выручки"}],
            requested_documents=["Выписки"],
        ),
    )
    expire = ExpireInfoRequests(SqlAlchemyUnitOfWork(sessionmaker), SystemClock())

    assert await expire() == 0
    await shift(
        sessionmaker,
        application_table,
        status_changed_at=datetime.now(UTC) - timedelta(days=31),
    )
    assert await expire() == 1

    card = (await client.get(f"/api/v1/applications/{application_id}")).json()
    assert card["status"]["code"] == "CANCELLED"
    assert card["events"][-1]["actor"] == "system"


async def test_stuck_applications_are_requeued(
    client: httpx.AsyncClient,
    login: Login,
    task_queue: FakeTaskQueue,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    application_id = await submitted(client)
    task_queue.processing.clear()
    requeue = RequeueStuck(
        SqlAlchemyUnitOfWork(sessionmaker), SystemClock(), task_queue
    )

    assert await requeue() == 0
    await shift(
        sessionmaker,
        application_table,
        status_changed_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    assert await requeue() == 1
    assert task_queue.processing == [UUID(application_id)]


async def test_readiness_reports_each_dependency(client: httpx.AsyncClient) -> None:
    response = await client.get("/ready")

    body = response.json()
    assert set(body["checks"]) == {"postgres", "redis", "keycloak", "scoring"}
    assert body["checks"]["postgres"] == "ok"
    assert response.status_code == (200 if body["status"] == "ready" else 503)


async def test_request_id_is_echoed(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "demo-42"})

    assert response.headers["x-request-id"] == "demo-42"
    assert (await client.get("/health")).headers["x-request-id"]
