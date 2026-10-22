from typing import Any, Final
from uuid import UUID

from taskiq import AsyncBroker
from taskiq.kicker import AsyncKicker

from application.interfaces.tasks import TaskQueue

PROCESS_APPLICATION_TASK: Final = "process_application"
DISBURSE_TASK: Final = "disburse"


class TaskiqTaskQueue(TaskQueue):
    def __init__(self, broker: AsyncBroker) -> None:
        self._broker = broker

    async def enqueue_processing(self, application_id: UUID) -> None:
        await self._kick(PROCESS_APPLICATION_TASK, str(application_id))

    async def enqueue_disbursement(self, application_id: UUID) -> None:
        await self._kick(DISBURSE_TASK, str(application_id))

    async def _kick(self, task_name: str, *args: Any) -> None:
        kicker: AsyncKicker[Any, Any] = AsyncKicker(
            task_name=task_name, broker=self._broker, labels={}
        )
        await kicker.kiq(*args)
