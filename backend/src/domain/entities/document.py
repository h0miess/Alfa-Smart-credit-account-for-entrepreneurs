from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final
from uuid import UUID


class DocumentKind(StrEnum):
    TAX_CERTIFICATE = "tax_certificate"
    BANK_STATEMENTS = "bank_statements"
    COLLATERAL_INFO = "collateral_info"


class DocumentStatus(StrEnum):
    ACCEPTED = "accepted"


@dataclass(frozen=True, slots=True)
class DocumentRequest:
    reason_code: str
    kind: DocumentKind
    title: str


# Дозапросы из ml/src/credit_scoring/decision.py → какой документ их закрывает
DOCUMENT_REQUESTS: Final[Mapping[str, DocumentRequest]] = MappingProxyType(
    {
        request.reason_code: request
        for request in (
            DocumentRequest(
                "INFO_TAX_ARREARS",
                DocumentKind.TAX_CERTIFICATE,
                "Справка ФНС об исполнении обязанности по уплате налогов "
                "или подтверждение погашения",
            ),
            DocumentRequest(
                "INFO_LOW_TURNOVER",
                DocumentKind.BANK_STATEMENTS,
                "Выписка по счетам в других банках за 12 месяцев",
            ),
            DocumentRequest(
                "INFO_NO_COLLATERAL",
                DocumentKind.COLLATERAL_INFO,
                "Сведения о предлагаемом залоге (объект, оценочная стоимость)",
            ),
        )
    }
)

ALLOWED_CONTENT_TYPES: Final = frozenset(
    {"application/pdf", "image/jpeg", "image/png", "text/csv"}
)
MAX_DOCUMENT_SIZE: Final = 10 * 1024 * 1024


@dataclass(eq=False, kw_only=True)
class Document:
    id: UUID
    application_id: UUID
    kind: DocumentKind
    reason_code: str
    file_ref: str
    file_name: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    extracted: dict[str, Any] = field(default_factory=dict)
    uploaded_at: datetime
