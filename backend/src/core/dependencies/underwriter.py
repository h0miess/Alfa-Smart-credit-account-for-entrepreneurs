from typing import Annotated

from fastapi import Depends

from application.interfaces.clock import Clock
from application.interfaces.scoring import ScoringGateway
from application.interfaces.uow import UnitOfWork
from application.use_cases.underwriter.decide import DecideApplication
from application.use_cases.underwriter.review import (
    GetReviewQueue,
    GetUnderwriterCard,
)
from core.dependencies.common import get_clock, get_scoring, get_uow

Uow = Annotated[UnitOfWork, Depends(get_uow)]


def get_review_queue(uow: Uow) -> GetReviewQueue:
    return GetReviewQueue(uow)


def get_underwriter_card(uow: Uow) -> GetUnderwriterCard:
    return GetUnderwriterCard(uow)


def get_decide(
    uow: Uow,
    scoring: Annotated[ScoringGateway, Depends(get_scoring)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> DecideApplication:
    return DecideApplication(uow, scoring, clock)
