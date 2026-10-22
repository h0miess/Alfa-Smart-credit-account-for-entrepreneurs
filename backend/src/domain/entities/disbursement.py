from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(eq=False, kw_only=True)
class Disbursement:
    id: UUID
    contract_id: UUID
    amount: Decimal
    account: str
    external_id: str
    at: datetime
