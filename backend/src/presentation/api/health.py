from dataclasses import dataclass

from fastapi import APIRouter
from starlette import status

health_router = APIRouter(tags=["service"])


@dataclass(frozen=True, slots=True)
class HealthResponse:
    status: str


@health_router.get(
    "/health",
    operation_id="getHealth",
    status_code=status.HTTP_200_OK,
)
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok")
