from typing import Protocol
from uuid import UUID


class TaskQueue(Protocol):
    async def enqueue_processing(self, application_id: UUID) -> None: ...

    async def enqueue_disbursement(self, application_id: UUID) -> None: ...
