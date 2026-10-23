import asyncio
import contextlib
import json
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from application.interfaces.events import ApplicationEventStream, StatusChanged
from domain.statuses import ApplicationStatus
from infra.postgres.uow import APPLICATION_EVENTS_CHANNEL

logger = logging.getLogger("credit_cabinet.notify")

RECONNECT_DELAY_IN_SECONDS = 2.0
CONNECT_TIMEOUT_IN_SECONDS = 5.0


class PostgresEventListener(ApplicationEventStream):
    def __init__(self, dsn: str, channel: str = APPLICATION_EVENTS_CHANNEL) -> None:
        self._dsn = dsn
        self._channel = channel
        self._subscribers: defaultdict[UUID, set[asyncio.Queue[StatusChanged]]] = (
            defaultdict(set)
        )
        self._task: asyncio.Task[None] | None = None
        self._connected = asyncio.Event()

    @asynccontextmanager
    async def subscribe(
        self, application_id: UUID
    ) -> AsyncIterator[AsyncIterator[StatusChanged]]:
        await self._ensure_started()
        queue: asyncio.Queue[StatusChanged] = asyncio.Queue()
        self._subscribers[application_id].add(queue)
        try:
            yield self._drain(queue)
        finally:
            self._subscribers[application_id].discard(queue)
            if not self._subscribers[application_id]:
                del self._subscribers[application_id]

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _drain(
        self, queue: asyncio.Queue[StatusChanged]
    ) -> AsyncIterator[StatusChanged]:
        while True:
            yield await queue.get()

    async def _ensure_started(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._connected.wait(), CONNECT_TIMEOUT_IN_SECONDS)

    async def _run(self) -> None:
        while True:
            try:
                await self._listen_until_closed()
                logger.warning("Соединение LISTEN закрыто, переподключаемся")
            except (OSError, asyncpg.PostgresError) as e:
                logger.error("Нет соединения для LISTEN: %r", e)
            await asyncio.sleep(RECONNECT_DELAY_IN_SECONDS)

    async def _listen_until_closed(self) -> None:
        closed = asyncio.Event()
        connection = await asyncpg.connect(self._dsn)
        try:
            connection.add_termination_listener(lambda _: closed.set())
            await connection.add_listener(self._channel, self._on_notify)
            self._connected.set()
            logger.info("Подписка LISTEN %s установлена", self._channel)
            await closed.wait()
        finally:
            await connection.close()

    def _on_notify(
        self, _connection: Any, _pid: int, _channel: str, payload: str
    ) -> None:
        data = json.loads(payload)
        event = StatusChanged(
            application_id=UUID(data["application_id"]),
            from_status=ApplicationStatus(data["from"]) if data["from"] else None,
            to_status=ApplicationStatus(data["to"]),
            at=datetime.fromisoformat(data["at"]),
        )
        for queue in self._subscribers.get(event.application_id, ()):
            queue.put_nowait(event)
