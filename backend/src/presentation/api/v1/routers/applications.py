from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Security
from starlette import status

from application.use_cases.client.applications import (
    CopyApplication,
    CreateDraft,
    DeleteDraft,
    DraftChanges,
    DraftData,
    GetApplicationCard,
    ListApplicationEvents,
    ListApplications,
    SubmitApplication,
    UpdateDraft,
)
from core.dependencies.auth import get_current_user_id
from core.dependencies.client import (
    get_application_card,
    get_copy,
    get_create_draft,
    get_delete_draft,
    get_list_applications,
    get_list_events,
    get_submit,
    get_update_draft,
)
from domain.entities.user import UserRole
from presentation.api.auth.bearer_scheme import bearer_scheme
from presentation.api.auth.roles import require_role
from presentation.api.exceptions.handlers import ExceptionSchema
from presentation.api.v1.schemas.applications import (
    ApplicationCardSchema,
    ApplicationSummarySchema,
    DraftCreateRequest,
    DraftUpdateRequest,
    EventSchema,
    SubmitRequest,
)

applications_router = APIRouter(
    prefix="/applications",
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


@applications_router.post(
    "",
    operation_id="createApplication",
    status_code=status.HTTP_201_CREATED,
)
async def create_application(
    body: DraftCreateRequest,
    user_id: UserId,
    use_case: Annotated[CreateDraft, Depends(get_create_draft)],
) -> ApplicationCardSchema:
    card = await use_case(
        user_id,
        DraftData(
            product=body.product,
            requested_amount=body.requested_amount,
            term_months=body.term_months,
            purpose=body.purpose,
            collateral_value=body.collateral_value,
            collateral_description=body.collateral_description,
        ),
    )
    return ApplicationCardSchema.build(card)


@applications_router.get("", operation_id="listApplications")
async def list_applications(
    user_id: UserId,
    use_case: Annotated[ListApplications, Depends(get_list_applications)],
) -> list[ApplicationSummarySchema]:
    return [ApplicationSummarySchema.build(s) for s in await use_case(user_id)]


@applications_router.get("/{application_id}", operation_id="getApplication")
async def get_application(
    application_id: UUID,
    user_id: UserId,
    use_case: Annotated[GetApplicationCard, Depends(get_application_card)],
) -> ApplicationCardSchema:
    return ApplicationCardSchema.build(await use_case(user_id, application_id))


@applications_router.patch("/{application_id}", operation_id="updateApplication")
async def update_application(
    application_id: UUID,
    body: DraftUpdateRequest,
    user_id: UserId,
    use_case: Annotated[UpdateDraft, Depends(get_update_draft)],
) -> ApplicationCardSchema:
    changes = DraftChanges(**body.model_dump(exclude_unset=True))
    return ApplicationCardSchema.build(await use_case(user_id, application_id, changes))


@applications_router.delete("/{application_id}", operation_id="deleteApplication")
async def delete_application(
    application_id: UUID,
    user_id: UserId,
    use_case: Annotated[DeleteDraft, Depends(get_delete_draft)],
) -> ApplicationCardSchema:
    return ApplicationCardSchema.build(await use_case(user_id, application_id))


@applications_router.post("/{application_id}/submit", operation_id="submitApplication")
async def submit_application(
    application_id: UUID,
    body: SubmitRequest,
    user_id: UserId,
    use_case: Annotated[SubmitApplication, Depends(get_submit)],
) -> ApplicationCardSchema:
    card = await use_case(
        user_id,
        application_id,
        consent_bki=body.consent_bki,
        consent_pd=body.consent_pd,
    )
    return ApplicationCardSchema.build(card)


@applications_router.get(
    "/{application_id}/events", operation_id="listApplicationEvents"
)
async def list_application_events(
    application_id: UUID,
    user_id: UserId,
    use_case: Annotated[ListApplicationEvents, Depends(get_list_events)],
) -> list[EventSchema]:
    return [EventSchema.build(e) for e in await use_case(user_id, application_id)]


@applications_router.post(
    "/{application_id}/copy",
    operation_id="copyApplication",
    status_code=status.HTTP_201_CREATED,
)
async def copy_application(
    application_id: UUID,
    user_id: UserId,
    use_case: Annotated[CopyApplication, Depends(get_copy)],
) -> ApplicationCardSchema:
    return ApplicationCardSchema.build(await use_case(user_id, application_id))
