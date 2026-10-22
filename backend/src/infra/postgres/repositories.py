from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from application.interfaces.repositories import (
    ApplicationRepository,
    CompanyRepository,
    ContractRepository,
    DecisionRepository,
    DisbursementRepository,
    DocumentRepository,
    EventRepository,
    OfferRepository,
    RepresentativeRepository,
    SnapshotRepository,
)
from domain.entities.application_event import ApplicationEvent
from domain.entities.company import Company
from domain.entities.contract import Contract
from domain.entities.decision import DecidedBy, Decision
from domain.entities.disbursement import Disbursement
from domain.entities.document import Document
from domain.entities.enrichment_snapshot import EnrichmentSnapshot
from domain.entities.loan_application import LoanApplication
from domain.entities.offer import Offer, OfferStatus
from domain.entities.representative import Representative
from domain.products import ProductCode
from domain.statuses import TERMINAL_STATUSES, ApplicationStatus
from infra.postgres.models import (
    application_event_table,
    application_table,
    contract_table,
    decision_table,
    disbursement_table,
    document_table,
    enrichment_snapshot_table,
    offer_table,
    representative_table,
)


class _SqlRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _add(self, entity: object) -> None:
        self._session.add(entity)
        await self._session.flush()


class SqlCompanyRepository(_SqlRepository, CompanyRepository):
    async def get(self, company_id: UUID) -> Company | None:
        return await self._session.get(Company, company_id)


class SqlRepresentativeRepository(_SqlRepository, RepresentativeRepository):
    async def get(self, representative_id: UUID) -> Representative | None:
        return await self._session.get(Representative, representative_id)

    async def get_by_keycloak_user_id(
        self, keycloak_user_id: UUID
    ) -> Representative | None:
        return await self._session.scalar(
            select(Representative).where(
                representative_table.c.keycloak_user_id == keycloak_user_id
            )
        )


class SqlApplicationRepository(_SqlRepository, ApplicationRepository):
    async def add(self, application: LoanApplication) -> None:
        await self._add(application)

    async def get(
        self, application_id: UUID, *, for_update: bool = False
    ) -> LoanApplication | None:
        query = select(LoanApplication).where(application_table.c.id == application_id)
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self._session.scalar(query)

    async def list_for_company(self, company_id: UUID) -> Sequence[LoanApplication]:
        result = await self._session.scalars(
            select(LoanApplication)
            .where(application_table.c.company_id == company_id)
            .order_by(application_table.c.created_at.desc())
        )
        return result.all()

    async def list_by_status(
        self,
        statuses: Sequence[ApplicationStatus],
        *,
        changed_before: datetime | None = None,
    ) -> Sequence[LoanApplication]:
        query = select(LoanApplication).where(application_table.c.status.in_(statuses))
        if changed_before is not None:
            query = query.where(application_table.c.status_changed_at < changed_before)
        result = await self._session.scalars(
            query.order_by(application_table.c.status_changed_at)
        )
        return result.all()

    async def has_active(self, company_id: UUID, product: ProductCode) -> bool:
        return bool(
            await self._session.scalar(
                select(
                    exists().where(
                        application_table.c.company_id == company_id,
                        application_table.c.product == product,
                        application_table.c.status.not_in(TERMINAL_STATUSES),
                    )
                )
            )
        )


class SqlEventRepository(_SqlRepository, EventRepository):
    async def list_for_application(
        self, application_id: UUID
    ) -> Sequence[ApplicationEvent]:
        result = await self._session.scalars(
            select(ApplicationEvent)
            .where(application_event_table.c.application_id == application_id)
            .order_by(application_event_table.c.seq)
        )
        return result.all()


class SqlDecisionRepository(_SqlRepository, DecisionRepository):
    async def add(self, decision: Decision) -> None:
        await self._add(decision)

    async def latest_for_application(self, application_id: UUID) -> Decision | None:
        return await self._session.scalar(
            select(Decision)
            .where(decision_table.c.application_id == application_id)
            .order_by(decision_table.c.at.desc())
            .limit(1)
        )

    async def latest_system_for_application(
        self, application_id: UUID
    ) -> Decision | None:
        return await self._session.scalar(
            select(Decision)
            .where(
                decision_table.c.application_id == application_id,
                decision_table.c.decided_by == DecidedBy.SYSTEM,
            )
            .order_by(decision_table.c.at.desc())
            .limit(1)
        )


class SqlSnapshotRepository(_SqlRepository, SnapshotRepository):
    async def add(self, snapshot: EnrichmentSnapshot) -> None:
        await self._add(snapshot)

    async def list_for_decision(
        self, decision_id: UUID
    ) -> Sequence[EnrichmentSnapshot]:
        result = await self._session.scalars(
            select(EnrichmentSnapshot)
            .where(enrichment_snapshot_table.c.decision_id == decision_id)
            .order_by(enrichment_snapshot_table.c.source)
        )
        return result.all()


class SqlOfferRepository(_SqlRepository, OfferRepository):
    async def add(self, offer: Offer) -> None:
        await self._add(offer)

    async def get_by_decision(self, decision_id: UUID) -> Offer | None:
        return await self._session.scalar(
            select(Offer).where(offer_table.c.decision_id == decision_id)
        )

    async def latest_for_application(
        self, application_id: UUID, *, for_update: bool = False
    ) -> Offer | None:
        query = (
            select(Offer)
            .join(decision_table, decision_table.c.id == offer_table.c.decision_id)
            .where(decision_table.c.application_id == application_id)
            .order_by(decision_table.c.at.desc())
            .limit(1)
        )
        if for_update:
            query = query.with_for_update(of=offer_table).execution_options(
                populate_existing=True
            )
        return await self._session.scalar(query)

    async def list_expired(self, today: date) -> Sequence[tuple[Offer, UUID]]:
        result = await self._session.execute(
            select(Offer, decision_table.c.application_id)
            .join(decision_table, decision_table.c.id == offer_table.c.decision_id)
            .where(
                offer_table.c.status == OfferStatus.ACTIVE,
                offer_table.c.valid_until < today,
            )
        )
        return [(offer, application_id) for offer, application_id in result.all()]


class SqlDocumentRepository(_SqlRepository, DocumentRepository):
    async def add(self, document: Document) -> None:
        await self._add(document)

    async def get(self, document_id: UUID) -> Document | None:
        return await self._session.get(Document, document_id)

    async def list_for_application(self, application_id: UUID) -> Sequence[Document]:
        result = await self._session.scalars(
            select(Document)
            .where(document_table.c.application_id == application_id)
            .order_by(document_table.c.uploaded_at)
        )
        return result.all()


class SqlContractRepository(_SqlRepository, ContractRepository):
    async def add(self, contract: Contract) -> None:
        await self._add(contract)

    async def get_by_offer(self, offer_id: UUID) -> Contract | None:
        return await self._session.scalar(
            select(Contract).where(contract_table.c.offer_id == offer_id)
        )


class SqlDisbursementRepository(_SqlRepository, DisbursementRepository):
    async def add(self, disbursement: Disbursement) -> None:
        await self._add(disbursement)

    async def get_by_contract(self, contract_id: UUID) -> Disbursement | None:
        return await self._session.scalar(
            select(Disbursement).where(disbursement_table.c.contract_id == contract_id)
        )
