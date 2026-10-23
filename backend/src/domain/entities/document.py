from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final
from uuid import UUID, uuid4

from domain.exceptions.base import BusinessRuleViolationError


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

    @classmethod
    def accept(
        cls,
        *,
        application_id: UUID,
        request: DocumentRequest,
        file_name: str,
        content_type: str,
        size_bytes: int,
        details: "DocumentDetails",
        at: datetime,
    ) -> "Document":
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise BusinessRuleViolationError(
                "Поддерживаются только PDF, JPG, PNG и CSV"
            )
        if not 0 < size_bytes <= MAX_DOCUMENT_SIZE:
            raise BusinessRuleViolationError("Размер файла — до 10 МБ")
        document_id = uuid4()
        return cls(
            id=document_id,
            application_id=application_id,
            kind=request.kind,
            reason_code=request.reason_code,
            file_ref=f"applications/{application_id}/{document_id}",
            file_name=file_name,
            content_type=content_type,
            size_bytes=size_bytes,
            status=DocumentStatus.ACCEPTED,
            extracted=details.extract(request),
            uploaded_at=at,
        )


@dataclass(frozen=True, slots=True)
class DocumentDetails:
    external_monthly_turnover: Decimal | None = None
    collateral_value: Decimal | None = None
    collateral_description: str | None = None

    def extract(self, request: DocumentRequest) -> dict[str, Any]:
        match request.kind:
            case DocumentKind.TAX_CERTIFICATE:
                return {"tax_arrears": False}
            case DocumentKind.BANK_STATEMENTS:
                if not self.external_monthly_turnover:
                    raise BusinessRuleViolationError(
                        "Укажите средние обороты в месяц по счетам в других банках"
                    )
                return {
                    "external_monthly_turnover": float(self.external_monthly_turnover)
                }
            case DocumentKind.COLLATERAL_INFO:
                if not self.collateral_value or not self.collateral_description:
                    raise BusinessRuleViolationError(
                        "Укажите предмет залога и его оценочную стоимость"
                    )
                return {
                    "collateral_value": float(self.collateral_value),
                    "collateral_description": self.collateral_description,
                }
