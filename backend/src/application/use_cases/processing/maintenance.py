import logging
from datetime import timedelta
from typing import Final

from application.interfaces.clock import Clock
from application.interfaces.tasks import TaskQueue
from application.interfaces.uow import UnitOfWork
from domain.entities.application_event import ActorType
from domain.entities.offer import OfferStatus
from domain.statuses import INFO_REQUEST_TTL, PROCESSING_SLA, ApplicationStatus

logger = logging.getLogger("credit_cabinet.maintenance")

STUCK_AFTER: Final = PROCESSING_SLA
STUCK_PROCESSING = (ApplicationStatus.SUBMITTED, ApplicationStatus.CHECKING)


class ExpireOffers:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(self) -> int:
        async with self._uow as uow:
            expired = await uow.offers.list_expired(self._clock.today())

        cancelled = 0
        for offer_id, application_id in [(o.id, a) for o, a in expired]:
            async with self._uow as uow:
                application = await uow.applications.get(
                    application_id, for_update=True
                )
                offer = await uow.offers.latest_for_application(
                    application_id, for_update=True
                )
                if (
                    application is None
                    or application.status is not ApplicationStatus.OFFERED
                    or offer is None
                    or offer.id != offer_id
                    or offer.status is not OfferStatus.ACTIVE
                ):
                    continue
                offer.expire()
                application.transition_to(
                    ApplicationStatus.CANCELLED,
                    actor=ActorType.SYSTEM,
                    actor_id=None,
                    at=self._clock.now(),
                    comment="Срок действия предложения истёк",
                )
                await uow.commit()
                cancelled += 1
        if cancelled:
            logger.info("Истекли предложения: %s", cancelled)
        return cancelled


class ExpireInfoRequests:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(self) -> int:
        deadline = self._clock.now() - INFO_REQUEST_TTL
        async with self._uow as uow:
            stale = await uow.applications.list_by_status(
                [ApplicationStatus.INFO_REQUESTED], changed_before=deadline
            )

        cancelled = 0
        for application_id in [a.id for a in stale]:
            async with self._uow as uow:
                application = await uow.applications.get(
                    application_id, for_update=True
                )
                if (
                    application is None
                    or application.status is not ApplicationStatus.INFO_REQUESTED
                    or application.status_changed_at >= deadline
                ):
                    continue
                application.transition_to(
                    ApplicationStatus.CANCELLED,
                    actor=ActorType.SYSTEM,
                    actor_id=None,
                    at=self._clock.now(),
                    comment="Документы не поступили за 30 дней",
                )
                await uow.commit()
                cancelled += 1
        if cancelled:
            logger.info("Отменены заявки без документов: %s", cancelled)
        return cancelled


class RequeueStuck:
    def __init__(
        self,
        uow: UnitOfWork,
        clock: Clock,
        tasks: TaskQueue,
        stuck_after: timedelta = STUCK_AFTER,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._tasks = tasks
        self._stuck_after = stuck_after

    async def __call__(self) -> int:
        changed_before = self._clock.now() - self._stuck_after
        async with self._uow as uow:
            processing = await uow.applications.list_by_status(
                STUCK_PROCESSING, changed_before=changed_before
            )
            signed = await uow.applications.list_by_status(
                [ApplicationStatus.SIGNED], changed_before=changed_before
            )

        for application in processing:
            await self._tasks.enqueue_processing(application.id)
        for application in signed:
            await self._tasks.enqueue_disbursement(application.id)

        requeued = len(processing) + len(signed)
        if requeued:
            logger.warning("Перезапущены зависшие заявки: %s", requeued)
        return requeued
