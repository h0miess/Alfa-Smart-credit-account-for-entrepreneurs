from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from domain.exceptions.base import BusinessRuleViolationError


class ProductCode(StrEnum):
    EXPRESS = "express"
    OVERDRAFT = "overdraft"
    INVESTMENT = "investment"


class LoanPurpose(StrEnum):
    WORKING_CAPITAL = "working_capital"
    EQUIPMENT = "equipment"
    CASH_GAP = "cash_gap"


PURPOSE_TITLES: Final[Mapping[LoanPurpose, str]] = MappingProxyType(
    {
        LoanPurpose.WORKING_CAPITAL: "Пополнить оборотные средства",
        LoanPurpose.EQUIPMENT: "Купить оборудование или транспорт",
        LoanPurpose.CASH_GAP: "Запас денег на счёте на кассовые разрывы",
    }
)

PURPOSE_PRODUCTS: Final[Mapping[LoanPurpose, tuple[ProductCode, ...]]] = (
    MappingProxyType(
        {
            LoanPurpose.WORKING_CAPITAL: (ProductCode.EXPRESS, ProductCode.OVERDRAFT),
            LoanPurpose.EQUIPMENT: (ProductCode.INVESTMENT,),
            LoanPurpose.CASH_GAP: (ProductCode.OVERDRAFT,),
        }
    )
)


@dataclass(frozen=True, slots=True)
class Product:
    code: ProductCode
    name: str
    min_amount: Decimal
    max_amount: Decimal
    min_term: int
    max_term: int
    rate_adj: Decimal
    secured_from: Decimal | None

    def check_terms(self, amount: Decimal, term_months: int) -> None:
        if not self.min_amount <= amount <= self.max_amount:
            raise BusinessRuleViolationError(
                f"Сумма для продукта «{self.name}» — "
                f"от {self.min_amount:,.0f} до {self.max_amount:,.0f} ₽".replace(
                    ",", " "
                )
            )
        if not self.min_term <= term_months <= self.max_term:
            raise BusinessRuleViolationError(
                f"Срок для продукта «{self.name}» — "
                f"от {self.min_term} до {self.max_term} мес."
            )

    def requires_collateral(self, amount: Decimal) -> bool:
        return self.secured_from is not None and amount > self.secured_from
