from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class EnrichmentSource(StrEnum):
    EGRUL = "egrul"
    FNS = "fns"
    BKI = "bki"
    STATEMENT = "statement"


@dataclass(eq=False, kw_only=True)
class EnrichmentSnapshot:
    id: UUID
    application_id: UUID
    source: EnrichmentSource
    payload: dict[str, Any]
    fetched_at: datetime
    decision_id: UUID | None = None
