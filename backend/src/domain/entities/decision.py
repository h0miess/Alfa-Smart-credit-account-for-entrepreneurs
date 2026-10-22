from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from domain.outcomes import Grade, ScoringOutcome


class DecidedBy(StrEnum):
    SYSTEM = "system"
    UNDERWRITER = "underwriter"


@dataclass(eq=False, kw_only=True)
class Decision:
    id: UUID
    application_id: UUID
    outcome: ScoringOutcome
    pd: Decimal | None
    grade: Grade | None
    score: int | None
    max_amount: Decimal | None
    reasons: list[dict[str, str]]
    risk_factors: list[dict[str, Any]] = field(default_factory=list)
    positive_factors: list[dict[str, Any]] = field(default_factory=list)
    requested_documents: list[dict[str, str]] = field(default_factory=list)
    decided_by: DecidedBy
    decided_by_user_id: UUID | None = None
    model_version: str | None
    policy_version: str | None
    request_payload: dict[str, Any] | None = None
    raw_response: dict[str, Any] | None = None
    comment: str | None = None
    at: datetime

    @property
    def manual_review_reasons(self) -> list[dict[str, str]]:
        return [r for r in self.reasons if r["code"].startswith("MR_")]
