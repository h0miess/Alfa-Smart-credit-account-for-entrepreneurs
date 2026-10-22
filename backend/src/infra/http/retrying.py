import logging
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from application.exceptions.external import ExternalServiceError

logger = logging.getLogger("credit_cabinet.http")


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code >= httpx.codes.INTERNAL_SERVER_ERROR
    )


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    service: str,
    attempts: int,
    timeout_seconds: float,
    **kwargs: Any,
) -> Any:
    retrying = AsyncRetrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=0.2, max=2),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
    try:
        async for attempt in retrying:
            with attempt:
                response = await client.request(
                    method, url, timeout=timeout_seconds, **kwargs
                )
                response.raise_for_status()
                return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(
            "%s ответил %s: %s", service, e.response.status_code, e.response.text
        )
        raise ExternalServiceError(service, f"HTTP {e.response.status_code}") from e
    except httpx.HTTPError as e:
        logger.error("%s недоступен: %r", service, e)
        raise ExternalServiceError(service, repr(e)) from e
