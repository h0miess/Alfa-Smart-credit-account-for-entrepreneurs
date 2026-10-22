from uuid import UUID

from fastapi import Request
from taskiq import TaskiqDepends

from core.dependencies.worker import build_process_application
from infra.tasks.broker import broker
from infra.tasks.queue import PROCESS_APPLICATION_TASK


@broker.task(task_name=PROCESS_APPLICATION_TASK)
async def process_application(
    application_id: str, request: Request = TaskiqDepends()
) -> None:
    await build_process_application(request.app.state)(UUID(application_id))
