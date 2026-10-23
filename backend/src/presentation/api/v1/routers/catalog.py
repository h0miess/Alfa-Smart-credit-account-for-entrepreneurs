from typing import Annotated, Any

from fastapi import APIRouter, Depends, Security
from starlette import status

from application.use_cases.client.catalog import (
    Calculate,
    ListProducts,
    RecommendProducts,
)
from core.dependencies.client import (
    get_calculate,
    get_list_products,
    get_recommend_products,
)
from domain.entities.user import UserRole
from domain.statuses import STATUS_VIEW
from presentation.api.auth.bearer_scheme import bearer_scheme
from presentation.api.auth.roles import require_role
from presentation.api.exceptions.handlers import ExceptionSchema
from presentation.api.v1.schemas.catalog import (
    PURPOSES,
    CalculationSchema,
    CalculatorRequest,
    ProductSchema,
    PurposeSchema,
    RecommendationSchema,
    RecommendRequest,
    StatusViewSchema,
)

catalog_router = APIRouter(
    dependencies=[
        Security(bearer_scheme),
        require_role(UserRole.CLIENT, UserRole.UNDERWRITER),
    ]
)

_ERRORS: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ExceptionSchema},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ExceptionSchema},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ExceptionSchema},
}


@catalog_router.get("/statuses", operation_id="listStatuses")
async def list_statuses() -> list[StatusViewSchema]:
    return [StatusViewSchema.build(view) for view in STATUS_VIEW.values()]


@catalog_router.get("/purposes", operation_id="listPurposes")
async def list_purposes() -> list[PurposeSchema]:
    return PURPOSES


@catalog_router.get("/products", operation_id="listProducts", responses=_ERRORS)
async def list_products(
    use_case: Annotated[ListProducts, Depends(get_list_products)],
) -> list[ProductSchema]:
    return [ProductSchema.build(terms) for terms in await use_case()]


@catalog_router.post(
    "/products/recommend", operation_id="recommendProducts", responses=_ERRORS
)
async def recommend_products(
    body: RecommendRequest,
    use_case: Annotated[RecommendProducts, Depends(get_recommend_products)],
) -> list[RecommendationSchema]:
    recommendations = await use_case(body.purpose, body.amount, body.term_months)
    return [RecommendationSchema.build(r) for r in recommendations]


@catalog_router.post("/calculator", operation_id="calculatePayment", responses=_ERRORS)
async def calculate_payment(
    body: CalculatorRequest,
    use_case: Annotated[Calculate, Depends(get_calculate)],
) -> CalculationSchema:
    calculation = await use_case(
        body.product, body.amount, body.term_months, body.collateral_value
    )
    return CalculationSchema.build(calculation)
