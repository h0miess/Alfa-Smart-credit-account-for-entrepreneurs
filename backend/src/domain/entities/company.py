from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class LegalForm(StrEnum):
    IP = "IP"
    OOO = "OOO"


class Industry(StrEnum):
    TRADE = "trade"
    SERVICES = "services"
    MANUFACTURING = "manufacturing"
    CONSTRUCTION = "construction"
    FOOD_SERVICE = "food_service"
    TRANSPORT = "transport"
    IT = "it"
    AGRICULTURE = "agriculture"


@dataclass(eq=False, kw_only=True)
class Company:
    id: UUID
    legal_form: LegalForm
    inn: str
    ogrn: str
    name: str
    industry: Industry
    region_tier: int
    registered_at: date
    employees: int
    bank_client_since: date
    annual_revenue: Decimal
    net_margin: Decimal
    settlement_account: str
