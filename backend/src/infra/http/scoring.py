import time
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import httpx

from application.interfaces.scoring import ModelInfo, ScoringGateway
from core.configs.services import ScoringSettings
from domain.products import Product, ProductCode
from infra.http.retrying import request_json

SERVICE_NAME = "скоринга"


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
