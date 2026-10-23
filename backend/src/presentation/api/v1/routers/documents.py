from decimal import Decimal
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, Security, UploadFile
from starlette import status

from application.use_cases.client.documents import (
    CompleteDocuments,
    DocumentContent,
    DownloadDocument,
    ListDocuments,
    UploadDocument,
    UploadedFile,
)
from core.dependencies.auth import get_current_user_id
from core.dependencies.client import (
    get_complete_documents,
    get_download_document,
    get_list_documents,
    get_upload_document,
)
from domain.entities.document import MAX_DOCUMENT_SIZE, DocumentDetails
from domain.entities.user import UserRole
from domain.exceptions.base import BusinessRuleViolationError
from presentation.api.auth.bearer_scheme import bearer_scheme
from presentation.api.auth.roles import require_role
from presentation.api.exceptions.handlers import ExceptionSchema
from presentation.api.v1.schemas.applications import (
    ApplicationCardSchema,
    DocumentSchema,
    DocumentsSchema,
)

documents_router = APIRouter(
    prefix="/applications/{application_id}/documents",
    dependencies=[Security(bearer_scheme), require_role(UserRole.CLIENT)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ExceptionSchema},
        status.HTTP_403_FORBIDDEN: {"model": ExceptionSchema},
        status.HTTP_404_NOT_FOUND: {"model": ExceptionSchema},
        status.HTTP_409_CONFLICT: {"model": ExceptionSchema},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ExceptionSchema},
    },
)

UserId = Annotated[UUID, Depends(get_current_user_id)]


def file_response(content: DocumentContent) -> Response:
    document = content.document
    return Response(
        content=content.data,
        media_type=document.content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(document.file_name)}"
            )
        },
    )


@documents_router.get("", operation_id="listDocuments")
async def list_documents(
    application_id: UUID,
    user_id: UserId,
    use_case: Annotated[ListDocuments, Depends(get_list_documents)],
) -> DocumentsSchema:
    return DocumentsSchema.build(await use_case(user_id, application_id))


@documents_router.post(
    "", operation_id="uploadDocument", status_code=status.HTTP_201_CREATED
)
async def upload_document(
    application_id: UUID,
    user_id: UserId,
    use_case: Annotated[UploadDocument, Depends(get_upload_document)],
    file: Annotated[UploadFile, File(description="PDF, JPG, PNG или CSV до 10 МБ")],
    reason_code: Annotated[str, Form(description="Какой дозапрос закрывает документ")],
    external_monthly_turnover: Annotated[Decimal | None, Form(gt=0)] = None,
    collateral_value: Annotated[Decimal | None, Form(gt=0)] = None,
    collateral_description: Annotated[str | None, Form(max_length=1000)] = None,
) -> DocumentSchema:
    data = await file.read(MAX_DOCUMENT_SIZE + 1)
    if len(data) > MAX_DOCUMENT_SIZE:
        raise BusinessRuleViolationError("Размер файла — до 10 МБ")
    document = await use_case(
        user_id,
        application_id,
        reason_code,
        UploadedFile(
            file_name=file.filename or "document",
            content_type=file.content_type or "application/octet-stream",
            data=data,
        ),
        DocumentDetails(
            external_monthly_turnover=external_monthly_turnover,
            collateral_value=collateral_value,
            collateral_description=collateral_description,
        ),
    )
    return DocumentSchema.build(document)


@documents_router.get(
    "/{document_id}/file",
    operation_id="downloadDocument",
    response_class=Response,
)
async def download_document(
    application_id: UUID,
    document_id: UUID,
    user_id: UserId,
    use_case: Annotated[DownloadDocument, Depends(get_download_document)],
) -> Response:
    return file_response(
        await use_case.for_client(user_id, application_id, document_id)
    )


@documents_router.post("/complete", operation_id="completeDocuments")
async def complete_documents(
    application_id: UUID,
    user_id: UserId,
    use_case: Annotated[CompleteDocuments, Depends(get_complete_documents)],
) -> ApplicationCardSchema:
    return ApplicationCardSchema.build(await use_case(user_id, application_id))
