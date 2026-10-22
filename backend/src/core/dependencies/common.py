from fastapi import Request

from application.interfaces.clock import Clock
from application.interfaces.scoring import ScoringGateway
from application.interfaces.tasks import TaskQueue
from application.interfaces.uow import UnitOfWork
from infra.clock import SystemClock
from infra.postgres.uow import SqlAlchemyUnitOfWork


def get_uow(request: Request) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(request.app.state.sessionmaker)


def get_clock() -> Clock:
    return SystemClock()


def get_scoring(request: Request) -> ScoringGateway:
    return request.app.state.scoring


def get_task_queue(request: Request) -> TaskQueue:
    return request.app.state.task_queue
