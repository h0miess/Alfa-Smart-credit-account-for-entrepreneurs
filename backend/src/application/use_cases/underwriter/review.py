from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from application.interfaces.uow import UnitOfWork
from domain.entities.application_event import ApplicationEvent
from domain.entities.company import Company
from domain.entities.decision import Decision
from domain.entities.document import Document
from domain.entities.enrichment_snapshot import EnrichmentSnapshot
from domain.entities.loan_application import LoanApplication
from domain.entities.offer import Offer
from domain.exceptions.base import NotFoundError
from domain.statuses import ApplicationStatus, eta_deadline


@dataclass(frozen=True, slots=True)
class QueueItem:
    application: LoanApplication
    company: Company
    eta_deadline: datetime | None
    decision: Decision | None


@dataclass(frozen=True, slots=True)
class UnderwriterCard:
    application: LoanApplication
    company: Company
    system_decision: Decision | None
    preliminary_offer: Offer | None
    latest_decision: Decision | None
    snapshots: Sequence[EnrichmentSnapshot]
    documents: Sequence[Document]
    events: Sequence[ApplicationEvent]
    eta_deadline: datetime | None


class GetReviewQueue:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self) -> Sequence[QueueItem]:
        async with self._uow as uow:
            applications = await uow.applications.list_by_status(
                [ApplicationStatus.MANUAL_REVIEW]
            )
            items = []
            for application in applications:
                company = await uow.companies.get(application.company_id)
                assert company is not None
                items.append(
                    QueueItem(
                        application=application,
                        company=company,
                        eta_deadline=eta_deadline(
                            application.status, application.status_changed_at
                        ),
                        decision=await uow.decisions.latest_system_for_application(
                            application.id
                        ),
                    )
                )
            return items


class GetUnderwriterCard:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, application_id: UUID) -> UnderwriterCard:
        async with self._uow as uow:
            application = await uow.applications.get(application_id)
            if application is None:
                raise NotFoundError("Заявка не найдена")
            company = await uow.companies.get(application.company_id)
            assert company is not None
            system_decision = await uow.decisions.latest_system_for_application(
                application.id
            )
            latest = await uow.decisions.latest_for_application(application.id)
            preliminary_offer, snapshots = None, []
            if system_decision is not None:
                preliminary_offer = await uow.offers.get_by_decision(system_decision.id)
                snapshots = list(
                    await uow.snapshots.list_for_decision(system_decision.id)
                )
            return UnderwriterCard(
                application=application,
                company=company,
                system_decision=system_decision,
                preliminary_offer=preliminary_offer,
                latest_decision=latest,
                snapshots=snapshots,
                documents=await uow.documents.list_for_application(application.id),
                events=await uow.events.list_for_application(application.id),
                eta_deadline=eta_deadline(
                    application.status, application.status_changed_at
                ),
            )
