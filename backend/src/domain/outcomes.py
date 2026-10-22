from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from domain.statuses import ApplicationStatus


class ScoringOutcome(StrEnum):
    APPROVED = "APPROVED"
    COUNTER_OFFER = "COUNTER_OFFER"
    REQUEST_INFO = "REQUEST_INFO"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    DECLINED = "DECLINED"


class Grade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


# Таблица process.md §5, сверяется тестом
OUTCOME_TO_STATUS: Final[Mapping[ScoringOutcome, ApplicationStatus]] = MappingProxyType(
    {
        ScoringOutcome.APPROVED: ApplicationStatus.OFFERED,
        ScoringOutcome.COUNTER_OFFER: ApplicationStatus.OFFERED,
        ScoringOutcome.REQUEST_INFO: ApplicationStatus.INFO_REQUESTED,
        ScoringOutcome.MANUAL_REVIEW: ApplicationStatus.MANUAL_REVIEW,
        ScoringOutcome.DECLINED: ApplicationStatus.DECLINED,
    }
)
