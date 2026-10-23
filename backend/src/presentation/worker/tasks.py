from typing import Any, Final
from uuid import UUID

from fastapi import Request
from taskiq import TaskiqDepends

from core.dependencies.worker import (
    build_disburse,
    build_expire_info_requests,
    build_expire_offers,
    build_process_application,
    build_requeue_stuck,
)
from infra.tasks.broker import broker
from infra.tasks.queue import DISBURSE_TASK, PROCESS_APPLICATION_TASK

EVERY_MINUTE: Final[list[dict[str, Any]]] = [{"cron": "* * * * *"}]


@broker.task(task_name=PROCESS_APPLICATION_TASK)
async def process_application(
    application_id: str, request: Request = TaskiqDepends()
) -> None:
    await build_process_application(request.app.state)(UUID(application_id))


@broker.task(task_name=DISBURSE_TASK)
async def disburse(application_id: str, request: Request = TaskiqDepends()) -> None:
    await build_disburse(request.app.state)(UUID(application_id))


@broker.task(task_name="expire_offers", schedule=EVERY_MINUTE)
async def expire_offers(request: Request = TaskiqDepends()) -> None:
    await build_expire_offers(request.app.state)()


@broker.task(task_name="expire_info_requests", schedule=EVERY_MINUTE)
async def expire_info_requests(request: Request = TaskiqDepends()) -> None:
    await build_expire_info_requests(request.app.state)()


@broker.task(task_name="requeue_stuck", schedule=EVERY_MINUTE)
async def requeue_stuck(request: Request = TaskiqDepends()) -> None:
    await build_requeue_stuck(request.app.state)()
