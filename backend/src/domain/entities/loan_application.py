from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from domain.entities.application_event import ActorType, ApplicationEvent
from domain.exceptions.base import ConflictError
from domain.exceptions.process import InvalidTransitionError
from domain.products import LoanPurpose, ProductCode
from domain.statuses import TERMINAL_STATUSES, TRANSITIONS, ApplicationStatus

COPYABLE_STATUSES = frozenset({ApplicationStatus.DECLINED, ApplicationStatus.CANCELLED})


@dataclass(eq=False, kw_only=True)
class LoanApplication:
    id: UUID
    company_id: UUID
    created_by: UUID
    product: ProductCode
    requested_amount: Decimal
    term_months: int
    purpose: LoanPurpose
    collateral_value: Decimal
    collateral_description: str | None
    status: ApplicationStatus
    consent_at: datetime | None
    created_at: datetime
    updated_at: datetime
    status_changed_at: datetime
    _events: list[ApplicationEvent] = field(
        default_factory=list, init=False, repr=False
    )

    @classmethod
    def create_draft(
        cls,
        *,
        company_id: UUID,
        created_by: UUID,
        actor_id: UUID,
        product: ProductCode,
        requested_amount: Decimal,
        term_months: int,
        purpose: LoanPurpose,
        collateral_value: Decimal,
        collateral_description: str | None,
        at: datetime,
    ) -> "LoanApplication":
        application = cls(
            id=uuid4(),
            company_id=company_id,
            created_by=created_by,
            product=product,
            requested_amount=requested_amount,
            term_months=term_months,
            purpose=purpose,
            collateral_value=collateral_value,
            collateral_description=collateral_description,
            status=ApplicationStatus.DRAFT,
            consent_at=None,
            created_at=at,
            updated_at=at,
            status_changed_at=at,
        )
        application._record(
            from_status=None,
            to_status=ApplicationStatus.DRAFT,
            actor=ActorType.CLIENT,
            actor_id=actor_id,
            comment=None,
            at=at,
        )
        return application

    def copy_as_draft(
        self, *, created_by: UUID, actor_id: UUID, at: datetime
    ) -> "LoanApplication":
        if self.status not in COPYABLE_STATUSES:
            raise ConflictError(
                "Новую заявку на основе этой можно создать только после отказа "
                "или отмены"
            )
        return LoanApplication.create_draft(
            company_id=self.company_id,
            created_by=created_by,
            actor_id=actor_id,
            product=self.product,
            requested_amount=self.requested_amount,
            term_months=self.term_months,
            purpose=self.purpose,
            collateral_value=self.collateral_value,
            collateral_description=self.collateral_description,
            at=at,
        )

    @property
    def is_active(self) -> bool:
        return self.status not in TERMINAL_STATUSES

    def update_draft(
        self,
        *,
        at: datetime,
        product: ProductCode | None = None,
        requested_amount: Decimal | None = None,
        term_months: int | None = None,
        purpose: LoanPurpose | None = None,
        collateral_value: Decimal | None = None,
        collateral_description: str | None = None,
    ) -> None:
        if self.status is not ApplicationStatus.DRAFT:
            raise ConflictError("Изменять можно только черновик заявки")
        if product is not None:
            self.product = product
        if requested_amount is not None:
            self.requested_amount = requested_amount
        if term_months is not None:
            self.term_months = term_months
        if purpose is not None:
            self.purpose = purpose
        if collateral_value is not None:
            self.collateral_value = collateral_value
        if collateral_description is not None:
            self.collateral_description = collateral_description
        self.updated_at = at

    def provide_collateral(
        self, *, value: Decimal, description: str, at: datetime
    ) -> None:
        if self.status is not ApplicationStatus.INFO_REQUESTED:
            raise ConflictError("Сведения о залоге принимаются только по дозапросу")
        self.collateral_value = value
        self.collateral_description = description
        self.updated_at = at

    def submit(self, *, actor_id: UUID, at: datetime) -> ApplicationEvent:
        event = self.transition_to(
            ApplicationStatus.SUBMITTED,
            actor=ActorType.CLIENT,
            actor_id=actor_id,
            at=at,
        )
        self.consent_at = at
        return event

    def transition_to(
        self,
        to_status: ApplicationStatus,
        *,
        actor: ActorType,
        actor_id: UUID | None,
        at: datetime,
        comment: str | None = None,
    ) -> ApplicationEvent:
        if to_status not in TRANSITIONS[self.status]:
            raise InvalidTransitionError(self.status, to_status)

        event = self._record(
            from_status=self.status,
            to_status=to_status,
            actor=actor,
            actor_id=actor_id,
            comment=comment,
            at=at,
        )
        self.status = to_status
        self.updated_at = at
        self.status_changed_at = at
        return event

    def pull_events(self) -> list[ApplicationEvent]:
        events, self._events = self._events, []
        return events

    def _record(
        self,
        *,
        from_status: ApplicationStatus | None,
        to_status: ApplicationStatus,
        actor: ActorType,
        actor_id: UUID | None,
        comment: str | None,
        at: datetime,
    ) -> ApplicationEvent:
        event = ApplicationEvent(
            id=uuid4(),
            application_id=self.id,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            actor_id=actor_id,
            comment=comment,
            at=at,
        )
        self._events.append(event)
        return event
