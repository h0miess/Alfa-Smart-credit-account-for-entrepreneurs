from types import TracebackType
from typing import Protocol, Self

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


class UnitOfWork(Protocol):
    companies: CompanyRepository
    representatives: RepresentativeRepository
    applications: ApplicationRepository
    events: EventRepository
    decisions: DecisionRepository
    snapshots: SnapshotRepository
    offers: OfferRepository
    documents: DocumentRepository
    contracts: ContractRepository
    disbursements: DisbursementRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...
