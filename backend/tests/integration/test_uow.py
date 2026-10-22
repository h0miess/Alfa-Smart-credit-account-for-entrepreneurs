import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.entities.loan_application import LoanApplication
from domain.exceptions.base import ConflictError
from domain.products import LoanPurpose, ProductCode
from domain.statuses import ApplicationStatus
from infra.postgres.uow import APPLICATION_EVENTS_CHANNEL, SqlAlchemyUnitOfWork

COMPANY_ID = UUID("00000000-0000-4000-8000-000000000201")
REPRESENTATIVE_ID = UUID("00000000-0000-4000-8000-000000000301")
NOW = datetime(2026, 10, 23, 10, 0, tzinfo=UTC)


def make_draft(product: ProductCode = ProductCode.EXPRESS) -> LoanApplication:
    return LoanApplication.create_draft(
        company_id=COMPANY_ID,
        created_by=REPRESENTATIVE_ID,
        actor_id=REPRESENTATIVE_ID,
        product=product,
        requested_amount=Decimal("1500000"),
        term_months=12,
        purpose=LoanPurpose.WORKING_CAPITAL,
        collateral_value=Decimal("0"),
        collateral_description=None,
        at=NOW,
    )


Notifications = asyncio.Queue[dict[str, str]]


@pytest.fixture
async def notifications(postgres_url: str) -> AsyncIterator[Notifications]:
    received: Notifications = asyncio.Queue()
    connection = await asyncpg.connect(postgres_url.replace("+asyncpg", ""))
    await connection.add_listener(
        APPLICATION_EVENTS_CHANNEL,
        lambda *args: received.put_nowait(json.loads(args[-1])),
    )
    yield received
    await connection.close()


async def test_transition_and_event_are_committed_together(
    sessionmaker: async_sessionmaker[AsyncSession],
    notifications: Notifications,
) -> None:
    draft = make_draft()
    async with SqlAlchemyUnitOfWork(sessionmaker) as uow:
        await uow.applications.add(draft)
        await uow.commit()

    async with SqlAlchemyUnitOfWork(sessionmaker) as uow:
        application = await uow.applications.get(draft.id, for_update=True)
        assert application is not None
        application.submit(actor_id=REPRESENTATIVE_ID, at=NOW)
        await uow.commit()

    async with SqlAlchemyUnitOfWork(sessionmaker) as uow:
        stored = await uow.applications.get(draft.id)
        events = await uow.events.list_for_application(draft.id)

    assert stored is not None
    assert stored.status is ApplicationStatus.SUBMITTED
    assert [(e.from_status, e.to_status) for e in events] == [
        (None, ApplicationStatus.DRAFT),
        (ApplicationStatus.DRAFT, ApplicationStatus.SUBMITTED),
    ]
    first = await asyncio.wait_for(notifications.get(), 5)
    second = await asyncio.wait_for(notifications.get(), 5)
    assert (first["to"], second["from"], second["to"]) == (
        "DRAFT",
        "DRAFT",
        "SUBMITTED",
    )
    assert second["application_id"] == str(draft.id)


async def test_rollback_discards_transition_event_and_notification(
    sessionmaker: async_sessionmaker[AsyncSession],
    notifications: Notifications,
) -> None:
    draft = make_draft()
    async with SqlAlchemyUnitOfWork(sessionmaker) as uow:
        await uow.applications.add(draft)
        await uow.commit()
    await asyncio.wait_for(notifications.get(), 5)

    async with SqlAlchemyUnitOfWork(sessionmaker) as uow:
        application = await uow.applications.get(draft.id, for_update=True)
        assert application is not None
        application.submit(actor_id=REPRESENTATIVE_ID, at=NOW)

    async with SqlAlchemyUnitOfWork(sessionmaker) as uow:
        stored = await uow.applications.get(draft.id)
        events = await uow.events.list_for_application(draft.id)

    assert stored is not None
    assert stored.status is ApplicationStatus.DRAFT
    assert len(events) == 1
    await asyncio.sleep(0.2)
    assert notifications.empty()


async def test_only_one_active_application_per_product(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with SqlAlchemyUnitOfWork(sessionmaker) as uow:
        await uow.applications.add(make_draft())
        await uow.applications.add(make_draft(ProductCode.OVERDRAFT))
        await uow.commit()

    with pytest.raises(ConflictError):
        async with SqlAlchemyUnitOfWork(sessionmaker) as uow:
            await uow.applications.add(make_draft())

    async with SqlAlchemyUnitOfWork(sessionmaker) as uow:
        assert await uow.applications.has_active(COMPANY_ID, ProductCode.EXPRESS)
        assert not await uow.applications.has_active(COMPANY_ID, ProductCode.INVESTMENT)
