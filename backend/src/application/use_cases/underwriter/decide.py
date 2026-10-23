from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from application.interfaces.clock import Clock
from application.interfaces.scoring import ScoringGateway
from application.interfaces.uow import UnitOfWork
from application.use_cases.client.catalog import find_product
from domain.entities.application_event import ActorType
from domain.entities.decision import DecidedBy, Decision
from domain.entities.document import DOCUMENT_REQUESTS, DocumentKind
from domain.entities.loan_application import LoanApplication
from domain.entities.offer import Offer
from domain.exceptions.base import (
    BusinessRuleViolationError,
    ConflictError,
    NotFoundError,
)
from domain.outcomes import OUTCOME_TO_STATUS, Grade, ScoringOutcome
from domain.pricing import GRADE_SPREAD, rate_for
from domain.statuses import ApplicationStatus


class UnderwriterAction(StrEnum):
    APPROVE = "approve"
    CHANGE_TERMS = "change_terms"
    REQUEST_INFO = "request_info"
    DECLINE = "decline"


@dataclass(frozen=True, slots=True)
class UnderwriterCommand:
    action: UnderwriterAction
    comment: str
    amount: Decimal | None = None
    term_months: int | None = None
    documents: Sequence[DocumentKind] = field(default_factory=tuple)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class _OfferTerms:
    amount: Decimal
    term_months: int
    rate: Decimal
    monthly_payment: Decimal | None = None


@dataclass(frozen=True, slots=True)
class _Verdict:
    outcome: ScoringOutcome
    client_text: str
    offer_terms: _OfferTerms | None = None
    requested_documents: list[dict[str, str]] = field(default_factory=list)


class DecideApplication:
    def __init__(self, uow: UnitOfWork, scoring: ScoringGateway, clock: Clock) -> None:
        self._uow = uow
        self._scoring = scoring
        self._clock = clock

    async def __call__(
        self, underwriter_id: UUID, application_id: UUID, command: UnderwriterCommand
    ) -> Decision:
        async with self._uow as uow:
            application = await uow.applications.get(application_id, for_update=True)
            if application is None:
                raise NotFoundError("Заявка не найдена")
            if application.status is not ApplicationStatus.MANUAL_REVIEW:
                raise ConflictError("Решение принимается только по заявке на проверке")

            system = await uow.decisions.latest_system_for_application(application.id)
            preliminary = (
                await uow.offers.get_by_decision(system.id) if system else None
            )
            verdict = await self._verdict(application, system, preliminary, command)

            now, today = self._clock.now(), self._clock.today()
            decision = Decision(
                id=uuid4(),
                application_id=application.id,
                outcome=verdict.outcome,
                pd=system.pd if system else None,
                grade=system.grade if system else None,
                score=system.score if system else None,
                max_amount=system.max_amount if system else None,
                reasons=[
                    {
                        "code": f"UW_{command.action.upper()}",
                        "text": verdict.client_text,
                    }
                ],
                risk_factors=system.risk_factors if system else [],
                positive_factors=system.positive_factors if system else [],
                requested_documents=verdict.requested_documents,
                decided_by=DecidedBy.UNDERWRITER,
                decided_by_user_id=underwriter_id,
                model_version=system.model_version if system else None,
                policy_version=system.policy_version if system else None,
                comment=command.comment,
                at=now,
            )
            await uow.decisions.add(decision)
            if (terms := verdict.offer_terms) is not None:
                await uow.offers.add(
                    Offer.create(
                        decision_id=decision.id,
                        product=application.product,
                        amount=terms.amount,
                        term_months=terms.term_months,
                        rate=terms.rate,
                        monthly_payment=terms.monthly_payment,
                        today=today,
                    )
                )
            application.transition_to(
                OUTCOME_TO_STATUS[verdict.outcome],
                actor=ActorType.UNDERWRITER,
                actor_id=underwriter_id,
                at=now,
                comment=verdict.client_text,
            )
            await uow.commit()
            return decision

    async def _verdict(
        self,
        application: LoanApplication,
        system: Decision | None,
        preliminary: Offer | None,
        command: UnderwriterCommand,
    ) -> _Verdict:
        match command.action:
            case UnderwriterAction.APPROVE:
                if preliminary is None:
                    raise BusinessRuleViolationError(
                        "У системы нет предварительного предложения: "
                        "укажите условия через change_terms"
                    )
                return _Verdict(
                    outcome=ScoringOutcome.APPROVED,
                    client_text="Заявку одобрил кредитный специалист",
                    offer_terms=_OfferTerms(
                        amount=preliminary.amount,
                        term_months=preliminary.term_months,
                        rate=preliminary.rate,
                        monthly_payment=preliminary.monthly_payment,
                    ),
                )
            case UnderwriterAction.CHANGE_TERMS:
                if command.amount is None or command.term_months is None:
                    raise BusinessRuleViolationError("Укажите сумму и срок")
                product = await find_product(self._scoring, application.product)
                product.check_terms(command.amount, command.term_months)
                rate = await self._rate(
                    application, system, preliminary, command.amount
                )
                same = (command.amount, command.term_months) == (
                    application.requested_amount,
                    application.term_months,
                )
                return _Verdict(
                    outcome=ScoringOutcome.APPROVED
                    if same
                    else ScoringOutcome.COUNTER_OFFER,
                    client_text="Кредитный специалист предложил условия по заявке",
                    offer_terms=_OfferTerms(command.amount, command.term_months, rate),
                )
            case UnderwriterAction.REQUEST_INFO:
                if not command.documents:
                    raise BusinessRuleViolationError("Выберите хотя бы один документ")
                requests = [
                    request
                    for request in DOCUMENT_REQUESTS.values()
                    if request.kind in set(command.documents)
                ]
                return _Verdict(
                    outcome=ScoringOutcome.REQUEST_INFO,
                    client_text="Кредитный специалист запросил документы",
                    requested_documents=[
                        {"reason_code": r.reason_code, "title": r.title}
                        for r in requests
                    ],
                )
            case UnderwriterAction.DECLINE:
                if not command.reason:
                    raise BusinessRuleViolationError(
                        "Укажите причину отказа для клиента"
                    )
                return _Verdict(
                    outcome=ScoringOutcome.DECLINED, client_text=command.reason
                )

    async def _rate(
        self,
        application: LoanApplication,
        system: Decision | None,
        preliminary: Offer | None,
        amount: Decimal,
    ) -> Decimal:
        if preliminary is not None:
            return preliminary.rate
        product = await find_product(self._scoring, application.product)
        key_rate = (await self._scoring.get_model_info()).key_rate
        grade = Grade.D
        if (
            system is not None
            and system.grade is not None
            and system.grade in GRADE_SPREAD
        ):
            grade = system.grade
        return rate_for(
            key_rate, grade, product.rate_adj, application.collateral_value / amount
        )
