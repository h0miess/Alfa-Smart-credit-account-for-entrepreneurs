from collections.abc import AsyncIterable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Security
from fastapi.sse import EventSourceResponse, ServerSentEvent
from starlette import status

from application.use_cases.client.watch import WatchApplication
from core.dependencies.auth import get_current_user_id
from core.dependencies.client import get_watch
from domain.entities.user import UserRole
from presentation.api.auth.bearer_scheme import bearer_scheme
from presentation.api.auth.roles import require_role
from presentation.api.exceptions.handlers import ExceptionSchema
from presentation.api.v1.schemas.applications import StatusUpdateSchema

stream_router = APIRouter(
    dependencies=[Security(bearer_scheme), require_role(UserRole.CLIENT)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ExceptionSchema},
        status.HTTP_404_NOT_FOUND: {"model": ExceptionSchema},
    },
)


async def watch_own_application(
    application_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[WatchApplication, Depends(get_watch)],
) -> WatchApplication:
    await use_case.ensure_access(user_id, application_id)
    return use_case


@stream_router.get(
    "/applications/{application_id}/stream",
    operation_id="streamApplicationStatus",
    response_class=EventSourceResponse,
)
async def stream_application_status(
    application_id: UUID,
    use_case: Annotated[WatchApplication, Depends(watch_own_application)],
) -> AsyncIterable[ServerSentEvent]:
    async for update in use_case(application_id):
        yield ServerSentEvent(
            event="status",
            id=update.changed.at.isoformat() if update.changed else None,
            data=StatusUpdateSchema.build(update),
        )
