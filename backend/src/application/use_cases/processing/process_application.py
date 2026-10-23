import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from application.decision_request import build_decision_request
from application.exceptions.external import ExternalServiceError
from application.interfaces.clock import Clock
from application.interfaces.scoring import ScoringGateway, ScoringResult
from application.interfaces.sources import (
    AbsGateway,
    BkiGateway,
    EgrulGateway,
    FnsGateway,
)
from application.interfaces.uow import UnitOfWork
from domain.entities.application_event import ActorType
from domain.entities.decision import DecidedBy, Decision
from domain.entities.document import DOCUMENT_REQUESTS
from domain.entities.enrichment_snapshot import EnrichmentSnapshot, EnrichmentSource
from domain.entities.offer import Offer
from domain.outcomes import OUTCOME_TO_STATUS, ScoringOutcome
from domain.statuses import ApplicationStatus

logger = logging.getLogger("credit_cabinet.processing")

PROCESSABLE_STATUSES = frozenset(
    {ApplicationStatus.SUBMITTED, ApplicationStatus.CHECKING}
)


@dataclass(frozen=True, slots=True)
class SourceData:
    payload: dict[str, Any]
    fetched_at: datetime


SYSTEM_UNAVAILABLE_REASON = {
    "code": "SYSTEM_UNAVAILABLE",
    "text": "Автоматическая проверка временно недоступна: заявку рассмотрит специалист",
}


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int = 5
    first_delay_in_seconds: float = 2.0

    def delay(self, attempt: int) -> float:
        return self.first_delay_in_seconds * 2 ** (attempt - 1)


DEFAULT_RETRY = RetryPolicy()


@dataclass(frozen=True, slots=True)
class Sources:
    egrul: EgrulGateway
    fns: FnsGateway
    bki: BkiGateway
    abs: AbsGateway


class ProcessApplication:
    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        sources: Sources,
        scoring: ScoringGateway,
        retry: RetryPolicy = DEFAULT_RETRY,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._sources = sources
        self._scoring = scoring
        self._retry = retry
        self._sleep = sleep

    async def __call__(self, application_id: UUID) -> None:
        for attempt in range(1, self._retry.attempts + 1):
            try:
                await self._process(application_id)
                return
            except ExternalServiceError as e:
                logger.warning(
                    "Сбой при обработке заявки {application_id=%s, attempt=%s}: %s",
                    application_id,
                    attempt,
                    e.details,
                )
                if attempt == self._retry.attempts:
                    await self._hand_over_to_underwriter(application_id, e)
                    return
                await self._sleep(self._retry.delay(attempt))

    async def _hand_over_to_underwriter(
        self, application_id: UUID, error: ExternalServiceError
    ) -> None:
        async with self._uow as uow:
            application = await uow.applications.get(application_id, for_update=True)
            if (
                application is None
                or application.status is not ApplicationStatus.CHECKING
            ):
                return
            now = self._clock.now()
            await uow.decisions.add(
                Decision(
                    id=uuid4(),
                    application_id=application.id,
                    outcome=ScoringOutcome.MANUAL_REVIEW,
                    pd=None,
                    grade=None,
                    score=None,
                    max_amount=None,
                    reasons=[SYSTEM_UNAVAILABLE_REASON],
                    decided_by=DecidedBy.SYSTEM,
                    model_version=None,
                    policy_version=None,
                    comment=f"{error}: {error.details}",
                    at=now,
                )
            )
            application.transition_to(
                ApplicationStatus.MANUAL_REVIEW,
                actor=ActorType.SYSTEM,
                actor_id=None,
                at=now,
                comment=SYSTEM_UNAVAILABLE_REASON["text"],
            )
            await uow.commit()
        logger.error(
            "Заявка передана андеррайтеру после сбоев {application_id=%s}",
            application_id,
        )

    async def _process(self, application_id: UUID) -> None:
        async with self._uow as uow:
            application = await uow.applications.get(application_id, for_update=True)
            if application is None or application.status not in PROCESSABLE_STATUSES:
                return
            if application.status is ApplicationStatus.SUBMITTED:
                application.transition_to(
                    ApplicationStatus.CHECKING,
                    actor=ActorType.SYSTEM,
                    actor_id=None,
                    at=self._clock.now(),
                )
                await uow.commit()
            company = await uow.companies.get(application.company_id)
            assert company is not None
            documents = await uow.documents.list_for_application(application.id)

        sources = await self._fetch_sources(company.inn)
        request = build_decision_request(
            application,
            company,
            {source: data.payload for source, data in sources.items()},
            documents,
            self._clock.today(),
        )
        result = await self._scoring.decide(request)

        async with self._uow as uow:
            application = await uow.applications.get(application_id, for_update=True)
            if (
                application is None
                or application.status is not ApplicationStatus.CHECKING
            ):
                return

            now = self._clock.now()
            decision = _decision(application.id, request, result, now)
            await uow.decisions.add(decision)
            for source, data in sources.items():
                await uow.snapshots.add(
                    EnrichmentSnapshot(
                        id=uuid4(),
                        application_id=application.id,
                        source=source,
                        payload=data.payload,
                        fetched_at=data.fetched_at,
                        decision_id=decision.id,
                    )
                )
            if result.offer is not None:
                await uow.offers.add(
                    Offer.create(
                        decision_id=decision.id,
                        product=result.offer.product,
                        amount=result.offer.amount,
                        term_months=result.offer.term_months,
                        rate=result.offer.rate,
                        monthly_payment=result.offer.monthly_payment,
                        today=self._clock.today(),
                    )
                )
            application.transition_to(
                OUTCOME_TO_STATUS[result.outcome],
                actor=ActorType.SYSTEM,
                actor_id=None,
                at=now,
                comment="; ".join(reason["text"] for reason in result.reasons),
            )
            await uow.commit()

        logger.info(
            "Заявка обработана {application_id=%s, outcome=%s}",
            application_id,
            result.outcome,
        )

    async def _fetch_sources(self, inn: str) -> dict[EnrichmentSource, SourceData]:
        calls: Mapping[EnrichmentSource, Awaitable[dict[str, Any]]] = {
            EnrichmentSource.EGRUL: self._sources.egrul.get_extract(inn),
            EnrichmentSource.FNS: self._sources.fns.get_arrears(inn),
            EnrichmentSource.BKI: self._sources.bki.get_report(inn),
            EnrichmentSource.STATEMENT: self._sources.abs.get_statement(inn),
        }
        payloads = await asyncio.gather(*calls.values())
        fetched_at = self._clock.now()
        return {
            source: SourceData(payload=payload, fetched_at=fetched_at)
            for source, payload in zip(calls, payloads, strict=True)
        }


def _decision(
    application_id: UUID,
    request: dict[str, Any],
    result: ScoringResult,
    at: datetime,
) -> Decision:
    info_reasons = [r for r in result.reasons if r["code"].startswith("INFO_")]
    requested = [
        {
            "reason_code": reason["code"],
            "title": (
                DOCUMENT_REQUESTS[reason["code"]].title
                if reason["code"] in DOCUMENT_REQUESTS
                else title
            ),
        }
        for reason, title in zip(info_reasons, result.requested_documents, strict=False)
    ]
    return Decision(
        id=uuid4(),
        application_id=application_id,
        outcome=result.outcome,
        pd=result.pd,
        grade=result.grade,
        score=result.score,
        max_amount=result.max_amount,
        reasons=result.reasons,
        risk_factors=result.risk_factors,
        positive_factors=result.positive_factors,
        requested_documents=requested,
        decided_by=DecidedBy.SYSTEM,
        model_version=result.model_version,
        policy_version=result.policy_version,
        request_payload=request,
        raw_response=result.raw,
        at=at,
    )
