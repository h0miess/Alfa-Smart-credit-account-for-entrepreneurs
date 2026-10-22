import logging
from uuid import UUID, uuid4

from application.interfaces.clock import Clock
from application.interfaces.sources import AbsGateway
from application.interfaces.uow import UnitOfWork
from domain.entities.application_event import ActorType
from domain.entities.disbursement import Disbursement
from domain.statuses import ApplicationStatus

logger = logging.getLogger("credit_cabinet.processing")


class Disburse:
    def __init__(self, uow: UnitOfWork, clock: Clock, abs_gateway: AbsGateway) -> None:
        self._uow = uow
        self._clock = clock
        self._abs = abs_gateway

    async def __call__(self, application_id: UUID) -> None:
        async with self._uow as uow:
            application = await uow.applications.get(application_id)
            if (
                application is None
                or application.status is not ApplicationStatus.SIGNED
            ):
                return
            offer = await uow.offers.latest_for_application(application.id)
            assert offer is not None
            contract = await uow.contracts.get_by_offer(offer.id)
            company = await uow.companies.get(application.company_id)
            assert contract is not None and company is not None
            existing = await uow.disbursements.get_by_contract(contract.id)

        operation = None
        if existing is None:
            operation = await self._abs.disburse(
                contract_id=contract.id,
                account=company.settlement_account,
                amount=contract.amount,
            )

        async with self._uow as uow:
            application = await uow.applications.get(application_id, for_update=True)
            if (
                application is None
                or application.status is not ApplicationStatus.SIGNED
            ):
                return
            now = self._clock.now()
            if (
                operation is not None
                and await uow.disbursements.get_by_contract(contract.id) is None
            ):
                await uow.disbursements.add(
                    Disbursement(
                        id=uuid4(),
                        contract_id=contract.id,
                        amount=operation.amount,
                        account=operation.account,
                        external_id=operation.operation_id,
                        at=now,
                    )
                )
            application.transition_to(
                ApplicationStatus.ISSUED,
                actor=ActorType.SYSTEM,
                actor_id=None,
                at=now,
                comment=f"Деньги зачислены на счёт {company.settlement_account}",
            )
            await uow.commit()

        logger.info("Кредит выдан {application_id=%s}", application_id)
