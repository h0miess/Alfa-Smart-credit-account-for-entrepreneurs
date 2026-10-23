import asyncio
import json
import socket
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

from domain.entities.user import UserRole
from tests.integration.pipeline import Login, submitted
from tests.users import IP_IVANOV, ROMASHKA_DIRECTOR


@pytest.fixture
async def server_url(app: FastAPI) -> AsyncIterator[str]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=port, lifespan="off", log_level="warning"
        )
    )
    task = asyncio.create_task(server.serve())
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    await task


async def read_events(response: httpx.Response, count: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line.removeprefix("data: ")))
            if len(events) == count:
                break
    return events


async def test_stream_sends_current_status_then_changes(
    client: httpx.AsyncClient, login: Login, server_url: str
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    card = (
        await client.post(
            "/api/v1/applications",
            json={
                "product": "express",
                "requested_amount": 1500000,
                "term_months": 12,
                "purpose": "working_capital",
            },
        )
    ).json()

    async with (
        httpx.AsyncClient(base_url=server_url, timeout=10) as live,
        live.stream("GET", f"/api/v1/applications/{card['id']}/stream") as response,
    ):
        assert response.headers["content-type"].startswith("text/event-stream")
        reader = asyncio.create_task(read_events(response, 2))
        await asyncio.sleep(0.3)
        await client.post(
            f"/api/v1/applications/{card['id']}/submit",
            json={"consent_bki": True, "consent_pd": True},
        )
        first, second = await asyncio.wait_for(reader, 10)

    assert first["status"]["code"] == "DRAFT"
    assert first["changed_at"] is None
    assert second["status"]["code"] == "SUBMITTED"
    assert second["from_status"] == "DRAFT"
    assert second["status"]["eta_deadline"] is not None


async def test_stream_of_foreign_application_is_not_found(
    client: httpx.AsyncClient, login: Login
) -> None:
    login(IP_IVANOV, UserRole.CLIENT)
    application_id = await submitted(client)

    login(ROMASHKA_DIRECTOR, UserRole.CLIENT)
    response = await client.get(f"/api/v1/applications/{application_id}/stream")

    assert response.status_code == 404
