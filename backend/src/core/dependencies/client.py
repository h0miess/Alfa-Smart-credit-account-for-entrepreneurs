from typing import Annotated

from fastapi import Depends

from application.interfaces.clock import Clock
from application.interfaces.scoring import ScoringGateway
from application.interfaces.tasks import TaskQueue
from application.interfaces.uow import UnitOfWork
from application.use_cases.client.applications import (
    CopyApplication,
    CreateDraft,
    DeleteDraft,
    GetApplicationCard,
    ListApplicationEvents,
    ListApplications,
    SubmitApplication,
    UpdateDraft,
)
from application.use_cases.client.catalog import (
    Calculate,
    ListProducts,
    RecommendProducts,
)
from application.use_cases.client.get_profile import GetProfile
from application.use_cases.client.offer import (
    AcceptOffer,
    GetContract,
    RejectOffer,
    RequestSignCode,
    SignContract,
)
from core.dependencies.common import get_clock, get_scoring, get_task_queue, get_uow

Uow = Annotated[UnitOfWork, Depends(get_uow)]
Scoring = Annotated[ScoringGateway, Depends(get_scoring)]
ClockDep = Annotated[Clock, Depends(get_clock)]
Tasks = Annotated[TaskQueue, Depends(get_task_queue)]


def get_profile_use_case(uow: Uow) -> GetProfile:
    return GetProfile(uow)


def get_list_products(scoring: Scoring) -> ListProducts:
    return ListProducts(scoring)


def get_recommend_products(scoring: Scoring) -> RecommendProducts:
    return RecommendProducts(scoring)


def get_calculate(scoring: Scoring) -> Calculate:
    return Calculate(scoring)


def get_create_draft(uow: Uow, scoring: Scoring, clock: ClockDep) -> CreateDraft:
    return CreateDraft(uow, scoring, clock)


def get_update_draft(uow: Uow, scoring: Scoring, clock: ClockDep) -> UpdateDraft:
    return UpdateDraft(uow, scoring, clock)


def get_delete_draft(uow: Uow, clock: ClockDep) -> DeleteDraft:
    return DeleteDraft(uow, clock)


def get_list_applications(uow: Uow) -> ListApplications:
    return ListApplications(uow)


def get_application_card(uow: Uow) -> GetApplicationCard:
    return GetApplicationCard(uow)


def get_list_events(uow: Uow) -> ListApplicationEvents:
    return ListApplicationEvents(uow)


def get_submit(
    uow: Uow, scoring: Scoring, clock: ClockDep, tasks: Tasks
) -> SubmitApplication:
    return SubmitApplication(uow, scoring, clock, tasks)


def get_copy(uow: Uow, clock: ClockDep) -> CopyApplication:
    return CopyApplication(uow, clock)


def get_accept_offer(uow: Uow, clock: ClockDep) -> AcceptOffer:
    return AcceptOffer(uow, clock)


def get_reject_offer(uow: Uow, clock: ClockDep) -> RejectOffer:
    return RejectOffer(uow, clock)


def get_contract(uow: Uow) -> GetContract:
    return GetContract(uow)


def get_request_sign_code(uow: Uow, clock: ClockDep) -> RequestSignCode:
    return RequestSignCode(uow, clock)


def get_sign_contract(uow: Uow, clock: ClockDep, tasks: Tasks) -> SignContract:
    return SignContract(uow, clock, tasks)
