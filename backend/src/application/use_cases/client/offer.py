from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from application.interfaces.clock import Clock
from application.interfaces.tasks import TaskQueue
from application.interfaces.uow import UnitOfWork
from application.use_cases.client.access import (
    get_own_application,
    get_representative,
)
from application.use_cases.client.card import ApplicationCard, load_card
from domain.entities.application_event import ActorType
from domain.entities.company import Company
from domain.entities.contract import Contract
from domain.entities.loan_application import LoanApplication
from domain.entities.offer import Offer
from domain.entities.representative import Representative
from domain.exceptions.base import ConflictError, NotFoundError
from domain.exceptions.process import OfferExpiredError
from domain.statuses import ApplicationStatus

SIGNED_STATUSES = frozenset({ApplicationStatus.SIGNED, ApplicationStatus.ISSUED})


async def _active_offer(
    uow: UnitOfWork, application: LoanApplication, *, for_update: bool = False
) -> Offer:
    offer = await uow.offers.latest_for_application(
        application.id, for_update=for_update
    )
    if offer is None:
        raise ConflictError("По заявке нет предложения")
    return offer


async def _contract(uow: UnitOfWork, offer: Offer) -> Contract:
    contract = await uow.contracts.get_by_offer(offer.id)
    if contract is None:
        raise NotFoundError("Договор ещё не сформирован: сначала примите предложение")
    return contract


class AcceptOffer:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(self, user_id: UUID, application_id: UUID) -> ApplicationCard:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(
                uow, representative, application_id, for_update=True
            )
            if application.status is ApplicationStatus.ACCEPTED:
                return await load_card(uow, application)
            if application.status is not ApplicationStatus.OFFERED:
                raise ConflictError("Принять можно только действующее предложение")

            offer = await _active_offer(uow, application, for_update=True)
            now, today = self._clock.now(), self._clock.today()
            if offer.is_expired(today):
                offer.expire()
                application.transition_to(
                    ApplicationStatus.CANCELLED,
                    actor=ActorType.SYSTEM,
                    actor_id=None,
                    at=now,
                    comment="Срок действия предложения истёк",
                )
                await uow.commit()
                raise OfferExpiredError()

            offer.accept(today)
            application.transition_to(
                ApplicationStatus.ACCEPTED,
                actor=ActorType.CLIENT,
                actor_id=user_id,
                at=now,
            )
            await uow.contracts.add(Contract.from_offer(offer, now))
            await uow.commit()
            return await load_card(uow, application)


class RejectOffer:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(self, user_id: UUID, application_id: UUID) -> ApplicationCard:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(
                uow, representative, application_id, for_update=True
            )
            if application.status is not ApplicationStatus.OFFERED:
                raise ConflictError(
                    "Отказаться можно только от действующего предложения"
                )

            offer = await _active_offer(uow, application, for_update=True)
            offer.reject()
            application.transition_to(
                ApplicationStatus.CANCELLED,
                actor=ActorType.CLIENT,
                actor_id=user_id,
                at=self._clock.now(),
                comment="Клиент отказался от предложения",
            )
            await uow.commit()
            return await load_card(uow, application)


@dataclass(frozen=True, slots=True)
class ContractView:
    application: LoanApplication
    contract: Contract
    offer: Offer
    company: Company
    signer: Representative | None


class GetContract:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_id: UUID, application_id: UUID) -> ContractView:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(uow, representative, application_id)
            offer = await _active_offer(uow, application)
            contract = await _contract(uow, offer)
            company = await uow.companies.get(application.company_id)
            assert company is not None
            signer = (
                await uow.representatives.get(contract.signed_by)
                if contract.signed_by
                else None
            )
            return ContractView(
                application=application,
                contract=contract,
                offer=offer,
                company=company,
                signer=signer,
            )


@dataclass(frozen=True, slots=True)
class SignCode:
    code: str
    expires_at: datetime


class RequestSignCode:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(self, user_id: UUID, application_id: UUID) -> SignCode:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(
                uow, representative, application_id, for_update=True
            )
            representative.ensure_can_sign()
            if application.status is not ApplicationStatus.ACCEPTED:
                raise ConflictError("Подписать можно договор по принятому предложению")

            contract = await _contract(uow, await _active_offer(uow, application))
            code = contract.issue_sign_code(self._clock.now())
            await uow.commit()
            assert contract.sign_code_expires_at is not None
            return SignCode(code=code, expires_at=contract.sign_code_expires_at)


class SignContract:
    def __init__(self, uow: UnitOfWork, clock: Clock, tasks: TaskQueue) -> None:
        self._uow = uow
        self._clock = clock
        self._tasks = tasks

    async def __call__(
        self, user_id: UUID, application_id: UUID, code: str
    ) -> ApplicationCard:
        async with self._uow as uow:
            representative = await get_representative(uow, user_id)
            application = await get_own_application(
                uow, representative, application_id, for_update=True
            )
            if application.status in SIGNED_STATUSES:
                return await load_card(uow, application)
            representative.ensure_can_sign()
            if application.status is not ApplicationStatus.ACCEPTED:
                raise ConflictError("Подписать можно договор по принятому предложению")

            offer = await _active_offer(uow, application)
            contract = await _contract(uow, offer)
            contract.ensure_matches(offer)
            now = self._clock.now()
            contract.sign(code=code, signer_id=representative.id, at=now)
            application.transition_to(
                ApplicationStatus.SIGNED,
                actor=ActorType.CLIENT,
                actor_id=user_id,
                at=now,
            )
            await uow.commit()
            card = await load_card(uow, application)

        await self._tasks.enqueue_disbursement(application.id)
        return card
