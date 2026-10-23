from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.statuses import ApplicationStatus


@dataclass(frozen=True, slots=True)
class StatusChanged:
    application_id: UUID
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    at: datetime


class ApplicationEventStream(Protocol):
    def subscribe(
        self, application_id: UUID
    ) -> AbstractAsyncContextManager[AsyncIterator[StatusChanged]]: ...
