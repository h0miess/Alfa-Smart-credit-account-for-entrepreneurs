from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID


class EgrulGateway(Protocol):
    async def get_extract(self, inn: str) -> dict[str, Any]: ...


class FnsGateway(Protocol):
    async def get_arrears(self, inn: str) -> dict[str, Any]: ...


class BkiGateway(Protocol):
    async def get_report(self, inn: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class DisbursementOperation:
    operation_id: str
    account: str
    amount: Decimal


class AbsGateway(Protocol):
    async def get_statement(self, inn: str) -> dict[str, Any]: ...

    async def disburse(
        self, *, contract_id: UUID, account: str, amount: Decimal
    ) -> DisbursementOperation: ...
