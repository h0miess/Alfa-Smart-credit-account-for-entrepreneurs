import json
from types import TracebackType
from typing import Final, Self

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.interfaces.uow import UnitOfWork
from domain.entities.application_event import ApplicationEvent
from domain.entities.loan_application import LoanApplication
from infra.postgres.repositories import (
    SqlApplicationRepository,
    SqlCompanyRepository,
    SqlContractRepository,
    SqlDecisionRepository,
    SqlDisbursementRepository,
    SqlDocumentRepository,
    SqlEventRepository,
    SqlOfferRepository,
    SqlRepresentativeRepository,
    SqlSnapshotRepository,
)

APPLICATION_EVENTS_CHANNEL: Final = "application_events"


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def __aenter__(self) -> Self:
        self._session = self._sessionmaker()
        self.companies = SqlCompanyRepository(self._session)
        self.representatives = SqlRepresentativeRepository(self._session)
        self.applications = SqlApplicationRepository(self._session)
        self.events = SqlEventRepository(self._session)
        self.decisions = SqlDecisionRepository(self._session)
        self.snapshots = SqlSnapshotRepository(self._session)
        self.offers = SqlOfferRepository(self._session)
        self.documents = SqlDocumentRepository(self._session)
        self.contracts = SqlContractRepository(self._session)
        self.disbursements = SqlDisbursementRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._session.close()

    async def commit(self) -> None:
        events = self._pull_events()
        self._session.add_all(events)
        await self._session.flush()
        for event in events:
            await self._session.execute(
                select(func.pg_notify(APPLICATION_EVENTS_CHANNEL, _payload(event)))
            )
        await self._session.commit()

    def _pull_events(self) -> list[ApplicationEvent]:
        tracked = {*self._session.new, *self._session.identity_map.values()}
        return [
            event
            for entity in tracked
            if isinstance(entity, LoanApplication)
            for event in entity.pull_events()
        ]


def _payload(event: ApplicationEvent) -> str:
    return json.dumps(
        {
            "application_id": str(event.application_id),
            "from": event.from_status,
            "to": event.to_status,
            "at": event.at.isoformat(),
        }
    )
