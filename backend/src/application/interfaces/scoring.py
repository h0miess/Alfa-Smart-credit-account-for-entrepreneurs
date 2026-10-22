from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from domain.products import Product


@dataclass(frozen=True, slots=True)
class ModelInfo:
    model_version: str
    policy_version: str
    key_rate: Decimal


class ScoringGateway(Protocol):
    async def get_products(self) -> Sequence[Product]: ...

    async def get_model_info(self) -> ModelInfo: ...
