import time
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from application.exceptions.external import ExternalServiceError
from application.interfaces.scoring import (
    ModelInfo,
    ScoredOffer,
    ScoringGateway,
    ScoringResult,
)
from core.configs.services import ScoringSettings
from domain.outcomes import Grade, ScoringOutcome
from domain.products import Product, ProductCode
from infra.http.retrying import request_json

SERVICE_NAME = "скоринга"


class DecisionRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: str | None = None
    legal_form: Literal["IP", "OOO"]
    industry: Literal[
        "trade",
        "services",
        "manufacturing",
        "construction",
        "food_service",
        "transport",
        "it",
        "agriculture",
    ]
    region_tier: int = Field(2, ge=1, le=3)
    business_age_months: int = Field(ge=0, le=1200)
    employees: int = Field(ge=0, le=10_000)
    annual_revenue: float = Field(gt=0)
    avg_monthly_turnover: float = Field(ge=0)
    turnover_volatility: float = Field(ge=0, le=5)
    turnover_trend_12m: float = Field(ge=-1, le=10)
    net_margin: float = Field(ge=-1, le=1)
    existing_debt: float = Field(0, ge=0)
    monthly_debt_payments: float = Field(0, ge=0)
    cash_withdrawal_share: float = Field(0, ge=0, le=1)
    top_counterparty_share: float = Field(0.3, ge=0, le=1)
    bank_client_months: int = Field(0, ge=0)
    bki_history_months: int = Field(0, ge=0)
    max_overdue_days_12m: int = Field(0, ge=0)
    overdue_count_24m: int = Field(0, ge=0)
    credit_inquiries_3m: int = Field(0, ge=0)
    tax_arrears: bool = False
    mass_address: bool = False
    director_changes_12m: int = Field(0, ge=0)
    product: Literal["express", "overdraft", "investment"]
    requested_amount: float = Field(gt=0)
    term_months: int = Field(ge=1, le=120)
    collateral_value: float = Field(0, ge=0)


class HttpScoringGateway(ScoringGateway):
    def __init__(self, client: httpx.AsyncClient, settings: ScoringSettings) -> None:
        self._client = client
        self._settings = settings
        self._products: tuple[float, Sequence[Product]] | None = None
        self._model_info: tuple[float, ModelInfo] | None = None

    async def get_products(self) -> Sequence[Product]:
        if self._products and not self._is_stale(self._products[0]):
            return self._products[1]

        data = await self._request("GET", "/v1/products")
        products = [_product(item) for item in data]
        self._products = (time.monotonic(), products)
        return products

    async def get_model_info(self) -> ModelInfo:
        if self._model_info and not self._is_stale(self._model_info[0]):
            return self._model_info[1]

        data = await self._request("GET", "/v1/model")
        info = ModelInfo(
            model_version=data["model_version"],
            policy_version=data["policy_version"],
            key_rate=Decimal(str(data["key_rate"])),
        )
        self._model_info = (time.monotonic(), info)
        return info

    async def decide(self, request: Mapping[str, Any]) -> ScoringResult:
        try:
            payload = DecisionRequestIn.model_validate(request).model_dump(mode="json")
        except ValidationError as e:
            raise ExternalServiceError(
                SERVICE_NAME, f"запрос не прошёл схему: {e}"
            ) from e

        data = await self._request("POST", "/v1/decision", json=payload)
        return _result(data)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        return await request_json(
            self._client,
            method,
            f"{self._settings.URL}{path}",
            service=SERVICE_NAME,
            attempts=self._settings.ATTEMPTS,
            timeout_seconds=self._settings.TIMEOUT_IN_SECONDS,
            **kwargs,
        )

    def _is_stale(self, fetched_at: float) -> bool:
        return time.monotonic() - fetched_at > self._settings.CATALOG_TTL_IN_SECONDS


def _product(item: dict[str, Any]) -> Product:
    secured_from = item.get("secured_from")
    return Product(
        code=ProductCode(item["code"]),
        name=item["name"],
        min_amount=Decimal(str(item["min_amount"])),
        max_amount=Decimal(str(item["max_amount"])),
        min_term=int(item["min_term"]),
        max_term=int(item["max_term"]),
        rate_adj=Decimal(str(item["rate_adj"])),
        secured_from=Decimal(str(secured_from)) if secured_from is not None else None,
    )


def _decimal(value: Any) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _result(data: dict[str, Any]) -> ScoringResult:
    offer = data.get("offer")
    return ScoringResult(
        outcome=ScoringOutcome(data["outcome"]),
        pd=_decimal(data.get("pd")),
        score=data.get("score"),
        grade=Grade(data["grade"]) if data.get("grade") else None,
        max_amount=_decimal(data.get("max_amount")),
        offer=(
            ScoredOffer(
                product=ProductCode(offer["product"]),
                amount=Decimal(str(offer["amount"])),
                term_months=int(offer["term_months"]),
                rate=Decimal(str(offer["rate"])),
                monthly_payment=Decimal(str(offer["monthly_payment"])),
            )
            if offer
            else None
        ),
        reasons=[{"code": r["code"], "text": r["text"]} for r in data["reasons"]],
        risk_factors=data.get("risk_factors", []),
        positive_factors=data.get("positive_factors", []),
        requested_documents=data.get("requested_documents", []),
        model_version=data.get("model_version"),
        policy_version=data.get("policy_version"),
        raw=data,
    )
