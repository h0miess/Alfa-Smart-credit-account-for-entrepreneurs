from fastapi import Request

from application.interfaces.clock import Clock
from application.interfaces.uow import UnitOfWork
from infra.clock import SystemClock
from infra.postgres.uow import SqlAlchemyUnitOfWork


def get_uow(request: Request) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(request.app.state.sessionmaker)


def get_clock() -> Clock:
    return SystemClock()
