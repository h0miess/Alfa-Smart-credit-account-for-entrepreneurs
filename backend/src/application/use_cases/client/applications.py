from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from application.interfaces.clock import Clock
from application.interfaces.scoring import ScoringGateway
from application.interfaces.tasks import TaskQueue
from application.interfaces.uow import UnitOfWork
from application.use_cases.client.access import (
    get_own_application,
    get_representative,
)
from application.use_cases.client.card import (
    ApplicationCard,
    ApplicationSummary,
    load_card,
    summarize,
)
from application.use_cases.client.catalog import find_product
from domain.entities.application_event import ActorType, ApplicationEvent
from domain.entities.loan_application import LoanApplication
from domain.exceptions.base import BusinessRuleViolationError, ConflictError
from domain.products import LoanPurpose, ProductCode
from domain.statuses import ApplicationStatus

IN_PROGRESS_STATUSES = frozenset(
    {ApplicationStatus.SUBMITTED, ApplicationStatus.CHECKING}
)


@dataclass(frozen=True, slots=True)
class DraftData:
    product: ProductCode
    requested_amount: Decimal
    term_months: int
    purpose: LoanPurpose
    collateral_value: Decimal
    collateral_description: str | None


@dataclass(frozen=True, slots=True)
class DraftChanges:
    product: ProductCode | None = None
    requested_amount: Decimal | None = None
    term_months: int | None = None
    purpose: LoanPurpose | None = None
    collateral_value: Decimal | None = None
    collateral_description: str | None = None


class CreateDraft:
    def __init__(self, uow: UnitOfWork, scoring: ScoringGateway, clock: Clock) -> None:
        self._uow = uow
        self._scoring = scoring
        self._clock = clock

    async def __call__(self, user_id: UUID, data: DraftData) -> ApplicationCard:
        product = await find_product(self._scoring, data.product)
        product.check_terms(data.requested_amount, data.term_months)

        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = LoanApplication.create_draft(
                company_id=representative.company_id,
                created_by=representative.id,
                actor_id=user_id,
                product=data.product,
                requested_amount=data.requested_amount,
                term_months=data.term_months,
                purpose=data.purpose,
                collateral_value=data.collateral_value,
                collateral_description=data.collateral_description,
                at=self._clock.now(),
            )
            await uow.applications.add(application)
            await uow.commit()
            return await load_card(uow, application)


class UpdateDraft:
    def __init__(self, uow: UnitOfWork, scoring: ScoringGateway, clock: Clock) -> None:
        self._uow = uow
        self._scoring = scoring
        self._clock = clock

    async def __call__(
        self, user_id: UUID, application_id: UUID, changes: DraftChanges
    ) -> ApplicationCard:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(
                uow, representative, application_id, for_update=True
            )
            product = await find_product(
                self._scoring, changes.product or application.product
            )
            product.check_terms(
                changes.requested_amount or application.requested_amount,
                changes.term_months or application.term_months,
            )
            application.update_draft(
                at=self._clock.now(),
                product=changes.product,
                requested_amount=changes.requested_amount,
                term_months=changes.term_months,
                purpose=changes.purpose,
                collateral_value=changes.collateral_value,
                collateral_description=changes.collateral_description,
            )
            await uow.commit()
            return await load_card(uow, application)


class DeleteDraft:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(self, user_id: UUID, application_id: UUID) -> ApplicationCard:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(
                uow, representative, application_id, for_update=True
            )
            if application.status is ApplicationStatus.CANCELLED:
                return await load_card(uow, application)
            if application.status is not ApplicationStatus.DRAFT:
                raise ConflictError("Удалить можно только черновик заявки")
            application.transition_to(
                ApplicationStatus.CANCELLED,
                actor=ActorType.CLIENT,
                actor_id=user_id,
                at=self._clock.now(),
                comment="Клиент удалил черновик",
            )
            await uow.commit()
            return await load_card(uow, application)


class ListApplications:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_id: UUID) -> Sequence[ApplicationSummary]:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            applications = await uow.applications.list_for_company(
                representative.company_id
            )
            return [summarize(application) for application in applications]


class GetApplicationCard:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_id: UUID, application_id: UUID) -> ApplicationCard:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(uow, representative, application_id)
            return await load_card(uow, application)


class ListApplicationEvents:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(
        self, user_id: UUID, application_id: UUID
    ) -> Sequence[ApplicationEvent]:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(uow, representative, application_id)
            return await uow.events.list_for_application(application.id)


class SubmitApplication:
    def __init__(
        self,
        uow: UnitOfWork,
        scoring: ScoringGateway,
        clock: Clock,
        tasks: TaskQueue,
    ) -> None:
        self._uow = uow
        self._scoring = scoring
        self._clock = clock
        self._tasks = tasks

    async def __call__(
        self,
        user_id: UUID,
        application_id: UUID,
        *,
        consent_bki: bool,
        consent_pd: bool,
    ) -> ApplicationCard:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(
                uow, representative, application_id, for_update=True
            )
            if application.status in IN_PROGRESS_STATUSES:
                return await load_card(uow, application)

            if not (consent_bki and consent_pd):
                raise BusinessRuleViolationError(
                    "Для отправки заявки нужны согласия на запрос в БКИ "
                    "и на обработку персональных данных"
                )
            product = await find_product(self._scoring, application.product)
            product.check_terms(application.requested_amount, application.term_months)

            application.submit(actor_id=user_id, at=self._clock.now())
            await uow.commit()
            card = await load_card(uow, application)

        await self._tasks.enqueue_processing(application.id)
        return card


class CopyApplication:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(self, user_id: UUID, application_id: UUID) -> ApplicationCard:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            source = await get_own_application(uow, representative, application_id)
            copy = source.copy_as_draft(
                created_by=representative.id, actor_id=user_id, at=self._clock.now()
            )
            await uow.applications.add(copy)
            await uow.commit()
            return await load_card(uow, copy)
