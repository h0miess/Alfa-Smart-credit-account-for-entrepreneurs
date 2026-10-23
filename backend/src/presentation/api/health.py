from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette import status

from core.configs import settings
from infra.readiness import http_check, postgres_check, redis_check, run_checks

health_router = APIRouter(tags=["service"])


@dataclass(frozen=True, slots=True)
class HealthResponse:
    status: str


@dataclass(frozen=True, slots=True)
class ReadinessResponse:
    status: str
    checks: dict[str, str]


@health_router.get(
    "/health",
    operation_id="getHealth",
    status_code=status.HTTP_200_OK,
)
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok")


@health_router.get(
    "/ready",
    operation_id="getReadiness",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def get_readiness(request: Request) -> JSONResponse:
    state = request.app.state
    checks = await run_checks(
        {
            "postgres": postgres_check(state.sessionmaker),
            "redis": redis_check(settings.redis.url),
            "keycloak": http_check(state.http_client, settings.auth.keycloak.url_jwk),
            "scoring": http_check(state.http_client, f"{settings.scoring.URL}/health"),
        }
    )
    ready = all(result == "ok" for result in checks.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK
        if ready
        else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )
