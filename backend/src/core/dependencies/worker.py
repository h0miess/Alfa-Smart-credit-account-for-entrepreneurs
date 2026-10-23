from starlette.datastructures import State

from application.use_cases.processing.disburse import Disburse
from application.use_cases.processing.maintenance import (
    ExpireInfoRequests,
    ExpireOffers,
    RequeueStuck,
)
from application.use_cases.processing.process_application import (
    ProcessApplication,
    Sources,
)
from infra.clock import SystemClock
from infra.postgres.uow import SqlAlchemyUnitOfWork


def build_process_application(state: State) -> ProcessApplication:
    return ProcessApplication(
        uow=SqlAlchemyUnitOfWork(state.sessionmaker),
        clock=SystemClock(),
        sources=Sources(egrul=state.egrul, fns=state.fns, bki=state.bki, abs=state.abs),
        scoring=state.scoring,
    )


def build_disburse(state: State) -> Disburse:
    return Disburse(
        uow=SqlAlchemyUnitOfWork(state.sessionmaker),
        clock=SystemClock(),
        abs_gateway=state.abs,
    )


def build_expire_offers(state: State) -> ExpireOffers:
    return ExpireOffers(SqlAlchemyUnitOfWork(state.sessionmaker), SystemClock())


def build_expire_info_requests(state: State) -> ExpireInfoRequests:
    return ExpireInfoRequests(SqlAlchemyUnitOfWork(state.sessionmaker), SystemClock())


def build_requeue_stuck(state: State) -> RequeueStuck:
    return RequeueStuck(
        SqlAlchemyUnitOfWork(state.sessionmaker), SystemClock(), state.task_queue
    )
