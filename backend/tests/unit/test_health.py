from collections.abc import AsyncIterator

import httpx
import pytest

from app import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_me_uses_mock_user_in_local_environment(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/me")

    assert response.status_code == 200
    body = response.json()
    assert body["uuid"] == "00000000-0000-4000-8000-000000000101"
    assert body["roles"] == ["client"]
