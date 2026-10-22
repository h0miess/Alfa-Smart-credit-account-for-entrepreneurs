from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from domain.statuses import ApplicationStatus


class ActorType(StrEnum):
    CLIENT = "client"
    SYSTEM = "system"
    UNDERWRITER = "underwriter"


@dataclass(eq=False, kw_only=True)
class ApplicationEvent:
    id: UUID
    application_id: UUID
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    actor: ActorType
    actor_id: UUID | None
    comment: str | None
    at: datetime
