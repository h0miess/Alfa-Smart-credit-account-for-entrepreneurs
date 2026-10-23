from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from application.use_cases.underwriter.decide import (
    UnderwriterAction,
    UnderwriterCommand,
)
from application.use_cases.underwriter.review import QueueItem, UnderwriterCard
from domain.entities.company import Company, Industry, LegalForm
from domain.entities.decision import DecidedBy, Decision
from domain.entities.document import DocumentKind
from domain.entities.enrichment_snapshot import EnrichmentSnapshot, EnrichmentSource
from domain.entities.offer import Offer, OfferStatus
from domain.outcomes import Grade, ScoringOutcome
from domain.products import LoanPurpose, ProductCode
from domain.statuses import STATUS_VIEW
from presentation.api.v1.schemas.applications import (
    DocumentSchema,
    EventSchema,
    ReasonSchema,
    StatusSchema,
)
from presentation.api.v1.schemas.catalog import StatusViewSchema

Comment = Annotated[str, Field(min_length=3, max_length=2000)]


class _Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: Comment


class ApproveRequest(_Decision):
    action: Literal[UnderwriterAction.APPROVE]


class ChangeTermsRequest(_Decision):
    action: Literal[UnderwriterAction.CHANGE_TERMS]
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    term_months: int = Field(ge=1, le=120)


class RequestInfoRequest(_Decision):
    action: Literal[UnderwriterAction.REQUEST_INFO]
    documents: list[DocumentKind] = Field(min_length=1)


class DeclineRequest(_Decision):
    action: Literal[UnderwriterAction.DECLINE]
    reason: Annotated[str, Field(min_length=3, max_length=500)]


UnderwriterDecisionRequest = Annotated[
    ApproveRequest | ChangeTermsRequest | RequestInfoRequest | DeclineRequest,
    Field(discriminator="action"),
]


def to_command(body: UnderwriterDecisionRequest) -> UnderwriterCommand:
    match body:
        case ChangeTermsRequest():
            return UnderwriterCommand(
                action=body.action,
                comment=body.comment,
                amount=body.amount,
                term_months=body.term_months,
            )
        case RequestInfoRequest():
            return UnderwriterCommand(
                action=body.action, comment=body.comment, documents=body.documents
            )
        case DeclineRequest():
            return UnderwriterCommand(
                action=body.action, comment=body.comment, reason=body.reason
            )
        case _:
            return UnderwriterCommand(action=body.action, comment=body.comment)


@dataclass(frozen=True, slots=True)
class UnderwriterCompanySchema:
    id: UUID
    name: str
    legal_form: LegalForm
    inn: str
    ogrn: str
    industry: Industry
    region_tier: int
    registered_at: date
    employees: int
    bank_client_since: date
    annual_revenue: float
    net_margin: float

    @classmethod
    def build(cls, company: Company) -> "UnderwriterCompanySchema":
        return cls(
            id=company.id,
            name=company.name,
            legal_form=company.legal_form,
            inn=company.inn,
            ogrn=company.ogrn,
            industry=company.industry,
            region_tier=company.region_tier,
            registered_at=company.registered_at,
            employees=company.employees,
            bank_client_since=company.bank_client_since,
            annual_revenue=float(company.annual_revenue),
            net_margin=float(company.net_margin),
        )


@dataclass(frozen=True, slots=True)
class UnderwriterDecisionSchema:
    id: UUID
    outcome: ScoringOutcome
    decided_by: DecidedBy
    pd: float | None
    grade: Grade | None
    score: int | None
    max_amount: float | None
    reasons: list[ReasonSchema]
    manual_review_reasons: list[ReasonSchema]
    risk_factors: list[dict[str, Any]]
    positive_factors: list[dict[str, Any]]
    requested_documents: list[dict[str, str]]
    comment: str | None
    model_version: str | None
    policy_version: str | None
    at: datetime

    @classmethod
    def build(cls, decision: Decision) -> "UnderwriterDecisionSchema":
        return cls(
            id=decision.id,
            outcome=decision.outcome,
            decided_by=decision.decided_by,
            pd=float(decision.pd) if decision.pd is not None else None,
            grade=decision.grade,
            score=decision.score,
            max_amount=float(decision.max_amount) if decision.max_amount else None,
            reasons=[ReasonSchema(**r) for r in decision.reasons],
            manual_review_reasons=[
                ReasonSchema(**r) for r in decision.manual_review_reasons
            ],
            risk_factors=decision.risk_factors,
            positive_factors=decision.positive_factors,
            requested_documents=decision.requested_documents,
            comment=decision.comment,
            model_version=decision.model_version,
            policy_version=decision.policy_version,
            at=decision.at,
        )


@dataclass(frozen=True, slots=True)
class OfferTermsSchema:
    id: UUID
    amount: float
    term_months: int
    rate: float
    monthly_payment: float
    valid_until: date
    status: OfferStatus

    @classmethod
    def build(cls, offer: Offer) -> "OfferTermsSchema":
        return cls(
            id=offer.id,
            amount=float(offer.amount),
            term_months=offer.term_months,
            rate=float(offer.rate),
            monthly_payment=float(offer.monthly_payment),
            valid_until=offer.valid_until,
            status=offer.status,
        )


@dataclass(frozen=True, slots=True)
class SnapshotSchema:
    source: EnrichmentSource
    payload: dict[str, Any]
    fetched_at: datetime

    @classmethod
    def build(cls, snapshot: EnrichmentSnapshot) -> "SnapshotSchema":
        return cls(
            source=snapshot.source,
            payload=snapshot.payload,
            fetched_at=snapshot.fetched_at,
        )


@dataclass(frozen=True, slots=True)
class QueueItemSchema:
    id: UUID
    company: str
    inn: str
    product: ProductCode
    requested_amount: float
    term_months: int
    waiting_since: datetime
    eta_deadline: datetime | None
    grade: Grade | None
    pd: float | None
    manual_review_reasons: list[ReasonSchema]

    @classmethod
    def build(cls, item: QueueItem) -> "QueueItemSchema":
        decision = item.decision
        return cls(
            id=item.application.id,
            company=item.company.name,
            inn=item.company.inn,
            product=item.application.product,
            requested_amount=float(item.application.requested_amount),
            term_months=item.application.term_months,
            waiting_since=item.application.status_changed_at,
            eta_deadline=item.eta_deadline,
            grade=decision.grade if decision else None,
            pd=float(decision.pd) if decision and decision.pd is not None else None,
            manual_review_reasons=(
                [ReasonSchema(**r) for r in decision.manual_review_reasons]
                if decision
                else []
            ),
        )


@dataclass(frozen=True, slots=True)
class UnderwriterCardSchema:
    id: UUID
    company: UnderwriterCompanySchema
    product: ProductCode
    requested_amount: float
    term_months: int
    purpose: LoanPurpose
    collateral_value: float
    collateral_description: str | None
    status: StatusSchema
    system_decision: UnderwriterDecisionSchema | None
    latest_decision: UnderwriterDecisionSchema | None
    preliminary_offer: OfferTermsSchema | None
    snapshots: list[SnapshotSchema]
    documents: list[DocumentSchema]
    events: list[EventSchema]

    @classmethod
    def build(cls, card: UnderwriterCard) -> "UnderwriterCardSchema":
        application = card.application
        view = StatusViewSchema.build(STATUS_VIEW[application.status])
        return cls(
            id=application.id,
            company=UnderwriterCompanySchema.build(card.company),
            product=application.product,
            requested_amount=float(application.requested_amount),
            term_months=application.term_months,
            purpose=application.purpose,
            collateral_value=float(application.collateral_value),
            collateral_description=application.collateral_description,
            status=StatusSchema(
                code=view.code,
                title=view.title,
                next_action=view.next_action,
                eta_text=view.eta_text,
                eta_deadline=card.eta_deadline,
            ),
            system_decision=(
                UnderwriterDecisionSchema.build(card.system_decision)
                if card.system_decision
                else None
            ),
            latest_decision=(
                UnderwriterDecisionSchema.build(card.latest_decision)
                if card.latest_decision
                else None
            ),
            preliminary_offer=(
                OfferTermsSchema.build(card.preliminary_offer)
                if card.preliminary_offer
                else None
            ),
            snapshots=[SnapshotSchema.build(s) for s in card.snapshots],
            documents=[DocumentSchema.build(d) for d in card.documents],
            events=[EventSchema.build(e) for e in card.events],
        )
