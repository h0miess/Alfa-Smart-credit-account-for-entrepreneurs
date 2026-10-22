from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from application.interfaces.uow import UnitOfWork
from domain.entities.application_event import ApplicationEvent
from domain.entities.contract import Contract
from domain.entities.decision import Decision
from domain.entities.document import Document
from domain.entities.loan_application import LoanApplication
from domain.entities.offer import Offer
from domain.outcomes import ScoringOutcome
from domain.statuses import STATUS_VIEW, ApplicationStatus, StatusView, eta_deadline

CLIENT_OFFER_OUTCOMES = frozenset(
    {ScoringOutcome.APPROVED, ScoringOutcome.COUNTER_OFFER}
)


@dataclass(frozen=True, slots=True)
class ApplicationCard:
    application: LoanApplication
    status_view: StatusView
    eta_deadline: datetime | None
    decision: Decision | None
    offer: Offer | None
    contract: Contract | None
    documents: Sequence[Document]
    requested_documents: Sequence[Mapping[str, str]]
    events: Sequence[ApplicationEvent]

    @property
    def is_counter_offer(self) -> bool:
        return (
            self.decision is not None
            and self.decision.outcome is ScoringOutcome.COUNTER_OFFER
        )


@dataclass(frozen=True, slots=True)
class ApplicationSummary:
    application: LoanApplication
    status_view: StatusView
    eta_deadline: datetime | None


async def load_card(uow: UnitOfWork, application: LoanApplication) -> ApplicationCard:
    decision = await uow.decisions.latest_for_application(application.id)
    offer = None
    if decision is not None and decision.outcome in CLIENT_OFFER_OUTCOMES:
        offer = await uow.offers.get_by_decision(decision.id)
    contract = await uow.contracts.get_by_offer(offer.id) if offer else None
    requested = (
        decision.requested_documents
        if decision is not None
        and application.status is ApplicationStatus.INFO_REQUESTED
        else []
    )
    return ApplicationCard(
        application=application,
        status_view=STATUS_VIEW[application.status],
        eta_deadline=eta_deadline(
            application.status,
            application.status_changed_at,
            offer.valid_until if offer else None,
        ),
        decision=decision,
        offer=offer,
        contract=contract,
        documents=await uow.documents.list_for_application(application.id),
        requested_documents=requested,
        events=await uow.events.list_for_application(application.id),
    )


def summarize(application: LoanApplication) -> ApplicationSummary:
    return ApplicationSummary(
        application=application,
        status_view=STATUS_VIEW[application.status],
        eta_deadline=eta_deadline(application.status, application.status_changed_at),
    )
