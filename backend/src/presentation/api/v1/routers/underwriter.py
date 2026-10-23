from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Response, Security
from starlette import status

from application.use_cases.client.documents import DownloadDocument
from application.use_cases.underwriter.decide import DecideApplication
from application.use_cases.underwriter.review import (
    GetReviewQueue,
    GetUnderwriterCard,
)
from core.dependencies.auth import get_current_user_id
from core.dependencies.client import get_download_document
from core.dependencies.underwriter import (
    get_decide,
    get_review_queue,
    get_underwriter_card,
)
from domain.entities.user import UserRole
from presentation.api.auth.bearer_scheme import bearer_scheme
from presentation.api.auth.roles import require_role
from presentation.api.exceptions.handlers import ExceptionSchema
from presentation.api.v1.routers.documents import file_response
from presentation.api.v1.schemas.underwriter import (
    QueueItemSchema,
    UnderwriterCardSchema,
    UnderwriterDecisionRequest,
    to_command,
)

underwriter_router = APIRouter(
    prefix="/underwriter",
    dependencies=[Security(bearer_scheme), require_role(UserRole.UNDERWRITER)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ExceptionSchema},
        status.HTTP_403_FORBIDDEN: {"model": ExceptionSchema},
        status.HTTP_404_NOT_FOUND: {"model": ExceptionSchema},
        status.HTTP_409_CONFLICT: {"model": ExceptionSchema},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ExceptionSchema},
    },
)


@underwriter_router.get("/queue", operation_id="getReviewQueue")
async def get_queue(
    use_case: Annotated[GetReviewQueue, Depends(get_review_queue)],
) -> list[QueueItemSchema]:
    return [QueueItemSchema.build(item) for item in await use_case()]


@underwriter_router.get(
    "/applications/{application_id}", operation_id="getUnderwriterCard"
)
async def get_card(
    application_id: UUID,
    use_case: Annotated[GetUnderwriterCard, Depends(get_underwriter_card)],
) -> UnderwriterCardSchema:
    return UnderwriterCardSchema.build(await use_case(application_id))


@underwriter_router.post(
    "/applications/{application_id}/decision", operation_id="decideApplication"
)
async def decide(
    application_id: UUID,
    body: Annotated[UnderwriterDecisionRequest, Body()],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    use_case: Annotated[DecideApplication, Depends(get_decide)],
    card: Annotated[GetUnderwriterCard, Depends(get_underwriter_card)],
) -> UnderwriterCardSchema:
    await use_case(user_id, application_id, to_command(body))
    return UnderwriterCardSchema.build(await card(application_id))


@underwriter_router.get(
    "/applications/{application_id}/documents/{document_id}/file",
    operation_id="downloadDocumentForReview",
    response_class=Response,
)
async def download_document(
    application_id: UUID,
    document_id: UUID,
    use_case: Annotated[DownloadDocument, Depends(get_download_document)],
) -> Response:
    return file_response(await use_case.for_underwriter(application_id, document_id))
