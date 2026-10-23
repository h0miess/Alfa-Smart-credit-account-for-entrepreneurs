import asyncio
from collections.abc import Awaitable, Callable, Mapping

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

CHECK_TIMEOUT_IN_SECONDS = 2.0

Check = Callable[[], Awaitable[None]]


def postgres_check(sessionmaker: async_sessionmaker[AsyncSession]) -> Check:
    async def check() -> None:
        async with sessionmaker() as session:
            await session.execute(text("SELECT 1"))

    return check


def redis_check(url: str) -> Check:
    async def check() -> None:
        client = Redis.from_url(url)
        try:
            await client.ping()
        finally:
            await client.aclose()

    return check


def http_check(client: httpx.AsyncClient, url: str) -> Check:
    async def check() -> None:
        response = await client.get(url, timeout=CHECK_TIMEOUT_IN_SECONDS)
        response.raise_for_status()

    return check


async def run_checks(checks: Mapping[str, Check]) -> dict[str, str]:
    async def run(check: Check) -> str:
        try:
            await asyncio.wait_for(check(), CHECK_TIMEOUT_IN_SECONDS)
        except Exception as e:
            return f"error: {type(e).__name__}"
        return "ok"

    results = await asyncio.gather(*(run(check) for check in checks.values()))
    return dict(zip(checks, results, strict=True))
