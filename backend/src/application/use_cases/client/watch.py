from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from application.interfaces.events import ApplicationEventStream, StatusChanged
from application.interfaces.uow import UnitOfWork
from application.use_cases.client.access import (
    get_own_application,
    get_representative,
)
from application.use_cases.client.card import load_card
from domain.statuses import StatusView


@dataclass(frozen=True, slots=True)
class StatusUpdate:
    application_id: UUID
    status_view: StatusView
    eta_deadline: datetime | None
    changed: StatusChanged | None


class WatchApplication:
    def __init__(self, uow: UnitOfWork, events: ApplicationEventStream) -> None:
        self._uow = uow
        self._events = events

    async def ensure_access(self, user_id: UUID, application_id: UUID) -> None:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            await get_own_application(uow, representative, application_id)

    async def __call__(self, application_id: UUID) -> AsyncIterator[StatusUpdate]:
        async with self._events.subscribe(application_id) as events:
            yield await self._current(application_id, None)
            async for changed in events:
                yield await self._current(application_id, changed)

    async def _current(
        self, application_id: UUID, changed: StatusChanged | None
    ) -> StatusUpdate:
        async with self._uow as uow:
            application = await uow.applications.get(application_id)
            assert application is not None
            card = await load_card(uow, application)
            return StatusUpdate(
                application_id=application_id,
                status_view=card.status_view,
                eta_deadline=card.eta_deadline,
                changed=changed,
            )
