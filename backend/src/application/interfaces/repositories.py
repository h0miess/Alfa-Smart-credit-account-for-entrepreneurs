from collections.abc import Sequence
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from domain.entities.application_event import ApplicationEvent
from domain.entities.company import Company
from domain.entities.contract import Contract
from domain.entities.decision import Decision
from domain.entities.disbursement import Disbursement
from domain.entities.document import Document
from domain.entities.enrichment_snapshot import EnrichmentSnapshot
from domain.entities.loan_application import LoanApplication
from domain.entities.offer import Offer
from domain.entities.representative import Representative
from domain.products import ProductCode
from domain.statuses import ApplicationStatus


class CompanyRepository(Protocol):
    async def get(self, company_id: UUID) -> Company | None: ...


class RepresentativeRepository(Protocol):
    async def get(self, representative_id: UUID) -> Representative | None: ...

    async def get_by_keycloak_user_id(
        self, keycloak_user_id: UUID
    ) -> Representative | None: ...


class ApplicationRepository(Protocol):
    async def add(self, application: LoanApplication) -> None: ...

    async def get(
        self, application_id: UUID, *, for_update: bool = False
    ) -> LoanApplication | None: ...

    async def list_for_company(self, company_id: UUID) -> Sequence[LoanApplication]: ...

    async def list_by_status(
        self,
        statuses: Sequence[ApplicationStatus],
        *,
        changed_before: datetime | None = None,
    ) -> Sequence[LoanApplication]: ...

    async def has_active(self, company_id: UUID, product: ProductCode) -> bool: ...


class EventRepository(Protocol):
    async def list_for_application(
        self, application_id: UUID
    ) -> Sequence[ApplicationEvent]: ...


class DecisionRepository(Protocol):
    async def add(self, decision: Decision) -> None: ...

    async def latest_for_application(self, application_id: UUID) -> Decision | None: ...

    async def latest_system_for_application(
        self, application_id: UUID
    ) -> Decision | None: ...


class SnapshotRepository(Protocol):
    async def add(self, snapshot: EnrichmentSnapshot) -> None: ...

    async def list_for_decision(
        self, decision_id: UUID
    ) -> Sequence[EnrichmentSnapshot]: ...


class OfferRepository(Protocol):
    async def add(self, offer: Offer) -> None: ...

    async def get_by_decision(self, decision_id: UUID) -> Offer | None: ...

    async def latest_for_application(
        self, application_id: UUID, *, for_update: bool = False
    ) -> Offer | None: ...

    async def list_expired(self, today: date) -> Sequence[tuple[Offer, UUID]]: ...


class DocumentRepository(Protocol):
    async def add(self, document: Document) -> None: ...

    async def get(self, document_id: UUID) -> Document | None: ...

    async def list_for_application(
        self, application_id: UUID
    ) -> Sequence[Document]: ...


class ContractRepository(Protocol):
    async def add(self, contract: Contract) -> None: ...

    async def get_by_offer(self, offer_id: UUID) -> Contract | None: ...


class DisbursementRepository(Protocol):
    async def add(self, disbursement: Disbursement) -> None: ...

    async def get_by_contract(self, contract_id: UUID) -> Disbursement | None: ...
