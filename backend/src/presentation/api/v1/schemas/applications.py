from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from application.use_cases.client.card import ApplicationCard, ApplicationSummary
from application.use_cases.client.watch import StatusUpdate
from domain.entities.application_event import ActorType, ApplicationEvent
from domain.entities.contract import Contract
from domain.entities.decision import Decision
from domain.entities.document import DOCUMENT_REQUESTS, Document, DocumentKind
from domain.entities.offer import NO_BUNDLED_PRODUCTS_NOTE, Offer, OfferStatus
from domain.outcomes import ScoringOutcome
from domain.products import LoanPurpose, ProductCode
from domain.statuses import ApplicationStatus
from presentation.api.v1.schemas.catalog import StatusViewSchema


class DraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: ProductCode
    requested_amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    term_months: int = Field(ge=1, le=120)
    purpose: LoanPurpose
    collateral_value: Decimal = Field(
        default=Decimal(0), ge=0, max_digits=16, decimal_places=2
    )
    collateral_description: str | None = Field(default=None, max_length=1000)


class DraftUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: ProductCode | None = None
    requested_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=16, decimal_places=2
    )
    term_months: int | None = Field(default=None, ge=1, le=120)
    purpose: LoanPurpose | None = None
    collateral_value: Decimal | None = Field(
        default=None, ge=0, max_digits=16, decimal_places=2
    )
    collateral_description: str | None = Field(default=None, max_length=1000)


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent_bki: bool
    consent_pd: bool


@dataclass(frozen=True, slots=True)
class StatusSchema(StatusViewSchema):
    eta_deadline: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReasonSchema:
    code: str
    text: str


@dataclass(frozen=True, slots=True)
class ClientDecisionSchema:
    outcome: ScoringOutcome
    reasons: list[ReasonSchema]
    risk_factors: list[str]
    positive_factors: list[str]
    decided_at: datetime

    @classmethod
    def build(cls, decision: Decision) -> "ClientDecisionSchema":
        return cls(
            outcome=decision.outcome,
            reasons=[
                ReasonSchema(code=r["code"], text=r["text"]) for r in decision.reasons
            ],
            risk_factors=_labels(decision.risk_factors),
            positive_factors=_labels(decision.positive_factors),
            decided_at=decision.at,
        )


@dataclass(frozen=True, slots=True)
class OfferSchema:
    id: UUID
    product: ProductCode
    amount: float
    term_months: int
    rate: float
    monthly_payment: float
    overpayment: float
    valid_until: date
    status: OfferStatus
    requested_amount: float
    requested_term_months: int
    is_counter_offer: bool
    note: str = NO_BUNDLED_PRODUCTS_NOTE

    @classmethod
    def build(cls, offer: Offer, card: ApplicationCard) -> "OfferSchema":
        return cls(
            id=offer.id,
            product=offer.product,
            amount=float(offer.amount),
            term_months=offer.term_months,
            rate=float(offer.rate),
            monthly_payment=float(offer.monthly_payment),
            overpayment=float(offer.overpayment),
            valid_until=offer.valid_until,
            status=offer.status,
            requested_amount=float(card.application.requested_amount),
            requested_term_months=card.application.term_months,
            is_counter_offer=card.is_counter_offer,
        )


@dataclass(frozen=True, slots=True)
class ContractSummarySchema:
    id: UUID
    amount: float
    term_months: int
    rate: float
    monthly_payment: float
    signed_at: datetime | None

    @classmethod
    def build(cls, contract: Contract) -> "ContractSummarySchema":
        return cls(
            id=contract.id,
            amount=float(contract.amount),
            term_months=contract.term_months,
            rate=float(contract.rate),
            monthly_payment=float(contract.monthly_payment),
            signed_at=contract.signed_at,
        )


@dataclass(frozen=True, slots=True)
class RequestedDocumentSchema:
    reason_code: str
    kind: DocumentKind | None
    title: str
    uploaded: bool


@dataclass(frozen=True, slots=True)
class DocumentSchema:
    id: UUID
    kind: DocumentKind
    reason_code: str
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime

    @classmethod
    def build(cls, document: Document) -> "DocumentSchema":
        return cls(
            id=document.id,
            kind=document.kind,
            reason_code=document.reason_code,
            file_name=document.file_name,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            uploaded_at=document.uploaded_at,
        )


@dataclass(frozen=True, slots=True)
class EventSchema:
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    actor: ActorType
    comment: str | None
    at: datetime

    @classmethod
    def build(cls, event: ApplicationEvent) -> "EventSchema":
        return cls(
            from_status=event.from_status,
            to_status=event.to_status,
            actor=event.actor,
            comment=event.comment,
            at=event.at,
        )


@dataclass(frozen=True, slots=True)
class ApplicationSummarySchema:
    id: UUID
    product: ProductCode
    requested_amount: float
    term_months: int
    status: StatusSchema
    created_at: datetime
    updated_at: datetime

    @classmethod
    def build(cls, summary: ApplicationSummary) -> "ApplicationSummarySchema":
        application = summary.application
        return cls(
            id=application.id,
            product=application.product,
            requested_amount=float(application.requested_amount),
            term_months=application.term_months,
            status=_status(summary.status_view, summary.eta_deadline),
            created_at=application.created_at,
            updated_at=application.updated_at,
        )


@dataclass(frozen=True, slots=True)
class ApplicationCardSchema:
    id: UUID
    product: ProductCode
    requested_amount: float
    term_months: int
    purpose: LoanPurpose
    collateral_value: float
    collateral_description: str | None
    status: StatusSchema
    consent_at: datetime | None
    created_at: datetime
    updated_at: datetime
    decision: ClientDecisionSchema | None
    offer: OfferSchema | None
    contract: ContractSummarySchema | None
    requested_documents: list[RequestedDocumentSchema]
    documents: list[DocumentSchema]
    events: list[EventSchema]

    @classmethod
    def build(cls, card: ApplicationCard) -> "ApplicationCardSchema":
        application = card.application
        return cls(
            id=application.id,
            product=application.product,
            requested_amount=float(application.requested_amount),
            term_months=application.term_months,
            purpose=application.purpose,
            collateral_value=float(application.collateral_value),
            collateral_description=application.collateral_description,
            status=_status(card.status_view, card.eta_deadline),
            consent_at=application.consent_at,
            created_at=application.created_at,
            updated_at=application.updated_at,
            decision=ClientDecisionSchema.build(card.decision)
            if card.decision
            else None,
            offer=OfferSchema.build(card.offer, card) if card.offer else None,
            contract=ContractSummarySchema.build(card.contract)
            if card.contract
            else None,
            requested_documents=_requested(card),
            documents=[DocumentSchema.build(d) for d in card.documents],
            events=[EventSchema.build(e) for e in card.events],
        )


def _status(view: Any, eta_deadline: datetime | None) -> StatusSchema:
    return StatusSchema(
        code=view.code,
        title=view.title,
        next_action=view.next_action,
        eta_text=view.eta_text,
        eta_deadline=eta_deadline,
    )


def _labels(factors: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(factor.get("label", factor.get("feature"))) for factor in factors]


def _requested(card: ApplicationCard) -> list[RequestedDocumentSchema]:
    uploaded = {document.reason_code for document in card.documents}
    result = []
    for item in card.requested_documents:
        request = DOCUMENT_REQUESTS.get(item["reason_code"])
        result.append(
            RequestedDocumentSchema(
                reason_code=item["reason_code"],
                kind=request.kind if request else None,
                title=item["title"],
                uploaded=item["reason_code"] in uploaded,
            )
        )
    return result


@dataclass(frozen=True, slots=True)
class StatusUpdateSchema:
    application_id: UUID
    status: StatusSchema
    from_status: ApplicationStatus | None
    changed_at: datetime | None

    @classmethod
    def build(cls, update: StatusUpdate) -> "StatusUpdateSchema":
        return cls(
            application_id=update.application_id,
            status=_status(update.status_view, update.eta_deadline),
            from_status=update.changed.from_status if update.changed else None,
            changed_at=update.changed.at if update.changed else None,
        )
