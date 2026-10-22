from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Security
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette import status

from application.use_cases.client.offer import (
    AcceptOffer,
    GetContract,
    RejectOffer,
    RequestSignCode,
    SignContract,
)
from core.dependencies.auth import get_current_user_id
from core.dependencies.client import (
    get_accept_offer,
    get_contract,
    get_reject_offer,
    get_request_sign_code,
    get_sign_contract,
)
from domain.entities.user import UserRole
from domain.products import PRODUCT_TITLES
from presentation.api.auth.bearer_scheme import bearer_scheme
from presentation.api.auth.roles import require_role
from presentation.api.exceptions.handlers import ExceptionSchema
from presentation.api.v1.schemas.applications import ApplicationCardSchema
from presentation.api.v1.schemas.contract import (
    ContractSchema,
    SignCodeSchema,
    SignRequest,
)

templates = Jinja2Templates(directory=Path(__file__).parents[2] / "templates")

offer_router = APIRouter(
    prefix="/applications/{application_id}",
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


@offer_router.post("/offer/accept", operation_id="acceptOffer")
async def accept_offer(
    application_id: UUID,
    user_id: UserId,
    use_case: Annotated[AcceptOffer, Depends(get_accept_offer)],
) -> ApplicationCardSchema:
    return ApplicationCardSchema.build(await use_case(user_id, application_id))


@offer_router.post("/offer/reject", operation_id="rejectOffer")
async def reject_offer(
    application_id: UUID,
    user_id: UserId,
    use_case: Annotated[RejectOffer, Depends(get_reject_offer)],
) -> ApplicationCardSchema:
    return ApplicationCardSchema.build(await use_case(user_id, application_id))


@offer_router.get("/contract", operation_id="getContract")
async def get_contract_details(
    application_id: UUID,
    user_id: UserId,
    use_case: Annotated[GetContract, Depends(get_contract)],
) -> ContractSchema:
    return ContractSchema.build(await use_case(user_id, application_id))


@offer_router.get(
    "/contract/document",
    operation_id="getContractDocument",
    response_class=HTMLResponse,
)
async def get_contract_document(
    request: Request,
    application_id: UUID,
    user_id: UserId,
    use_case: Annotated[GetContract, Depends(get_contract)],
) -> HTMLResponse:
    view = await use_case(user_id, application_id)
    contract = ContractSchema.build(view)
    return templates.TemplateResponse(
        request,
        "contract.html",
        {
            "company": view.company,
            "contract": {
                "number": contract.number,
                "product_name": PRODUCT_TITLES[contract.product],
                "amount": f"{contract.amount:,.2f}".replace(",", " "),
                "term_months": contract.term_months,
                "rate": f"{contract.rate:.2f}",
                "monthly_payment": f"{contract.monthly_payment:,.2f}".replace(",", " "),
                "overpayment": f"{contract.overpayment:,.2f}".replace(",", " "),
                "created_at": f"{contract.created_at:%d.%m.%Y}",
                "signed_at": (
                    f"{contract.signed_at:%d.%m.%Y %H:%M} UTC"
                    if contract.signed_at
                    else None
                ),
                "signer": contract.signed_by,
                "note": contract.note,
            },
        },
    )


@offer_router.post("/contract/sign-code", operation_id="requestSignCode")
async def request_sign_code(
    application_id: UUID,
    user_id: UserId,
    use_case: Annotated[RequestSignCode, Depends(get_request_sign_code)],
) -> SignCodeSchema:
    return SignCodeSchema.build(await use_case(user_id, application_id))


@offer_router.post("/contract/sign", operation_id="signContract")
async def sign_contract(
    application_id: UUID,
    body: SignRequest,
    user_id: UserId,
    use_case: Annotated[SignContract, Depends(get_sign_contract)],
) -> ApplicationCardSchema:
    return ApplicationCardSchema.build(
        await use_case(user_id, application_id, body.code)
    )
