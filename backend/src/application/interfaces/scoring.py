from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from domain.outcomes import Grade, ScoringOutcome
from domain.products import Product, ProductCode


@dataclass(frozen=True, slots=True)
class ModelInfo:
    model_version: str
    policy_version: str
    key_rate: Decimal


@dataclass(frozen=True, slots=True)
class ScoredOffer:
    product: ProductCode
    amount: Decimal
    term_months: int
    rate: Decimal
    monthly_payment: Decimal


@dataclass(frozen=True, slots=True)
class ScoringResult:
    outcome: ScoringOutcome
    pd: Decimal | None
    score: int | None
    grade: Grade | None
    max_amount: Decimal | None
    offer: ScoredOffer | None
    reasons: list[dict[str, str]]
    risk_factors: list[dict[str, Any]]
    positive_factors: list[dict[str, Any]]
    requested_documents: list[str]
    model_version: str | None
    policy_version: str | None
    raw: dict[str, Any] = field(repr=False)


class ScoringGateway(Protocol):
    async def get_products(self) -> Sequence[Product]: ...

    async def get_model_info(self) -> ModelInfo: ...

    async def decide(self, request: Mapping[str, Any]) -> ScoringResult: ...
