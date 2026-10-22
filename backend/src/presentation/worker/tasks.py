from uuid import UUID

from fastapi import Request
from taskiq import TaskiqDepends

from core.dependencies.worker import build_disburse, build_process_application
from infra.tasks.broker import broker
from infra.tasks.queue import DISBURSE_TASK, PROCESS_APPLICATION_TASK


@broker.task(task_name=PROCESS_APPLICATION_TASK)
async def process_application(
    application_id: str, request: Request = TaskiqDepends()
) -> None:
    await build_process_application(request.app.state)(UUID(application_id))


@broker.task(task_name=DISBURSE_TASK)
async def disburse(application_id: str, request: Request = TaskiqDepends()) -> None:
    await build_disburse(request.app.state)(UUID(application_id))
