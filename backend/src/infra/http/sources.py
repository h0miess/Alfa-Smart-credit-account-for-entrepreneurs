from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx

from application.interfaces.sources import (
    AbsGateway,
    BkiGateway,
    DisbursementOperation,
    EgrulGateway,
    FnsGateway,
)
from core.configs.services import MocksSettings
from infra.http.retrying import request_json


class _MocksClient:
    service: str

    def __init__(self, client: httpx.AsyncClient, settings: MocksSettings) -> None:
        self._client = client
        self._settings = settings

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        return await request_json(
            self._client,
            method,
            f"{self._settings.URL}{path}",
            service=self.service,
            attempts=self._settings.ATTEMPTS,
            timeout_seconds=self._settings.TIMEOUT_IN_SECONDS,
            **kwargs,
        )


class HttpEgrulGateway(_MocksClient, EgrulGateway):
    service = "ЕГРЮЛ/ЕГРИП"

    async def get_extract(self, inn: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", f"/egrul/{inn}")
        return result


class HttpFnsGateway(_MocksClient, FnsGateway):
    service = "ФНС"

    async def get_arrears(self, inn: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", f"/fns/{inn}/arrears")
        return result


class HttpBkiGateway(_MocksClient, BkiGateway):
    service = "БКИ"

    async def get_report(self, inn: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", f"/bki/{inn}/report")
        return result


class HttpAbsGateway(_MocksClient, AbsGateway):
    service = "АБС"

    async def get_statement(self, inn: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", f"/abs/{inn}/statement")
        return result

    async def disburse(
        self, *, contract_id: UUID, account: str, amount: Decimal
    ) -> DisbursementOperation:
        data = await self._request(
            "POST",
            "/abs/disbursements",
            json={
                "contract_id": str(contract_id),
                "account": account,
                "amount": str(amount),
            },
            headers={"Idempotency-Key": str(contract_id)},
        )
        return DisbursementOperation(
            operation_id=data["operation_id"],
            account=data["account"],
            amount=Decimal(str(data["amount"])),
        )
