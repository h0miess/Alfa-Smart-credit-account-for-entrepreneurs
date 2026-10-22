from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from domain.entities.application_event import ActorType
from domain.entities.loan_application import LoanApplication
from domain.exceptions.base import ConflictError
from domain.exceptions.process import InvalidTransitionError
from domain.products import LoanPurpose, ProductCode
from domain.statuses import TRANSITIONS, ApplicationStatus

NOW = datetime(2026, 10, 23, 10, 0, tzinfo=UTC)


def make_draft() -> LoanApplication:
    return LoanApplication.create_draft(
        company_id=uuid4(),
        created_by=uuid4(),
        product=ProductCode.EXPRESS,
        requested_amount=Decimal("1500000"),
        term_months=12,
        purpose=LoanPurpose.WORKING_CAPITAL,
        collateral_value=Decimal("0"),
        collateral_description=None,
        at=NOW,
    )


def test_draft_creation_is_journaled() -> None:
    application = make_draft()

    [event] = application.pull_events()
    assert application.status is ApplicationStatus.DRAFT
    assert event.from_status is None
    assert event.to_status is ApplicationStatus.DRAFT
    assert event.actor is ActorType.CLIENT


def test_each_transition_produces_one_event() -> None:
    application = make_draft()
    application.pull_events()
    path = [
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.CHECKING,
        ApplicationStatus.OFFERED,
        ApplicationStatus.ACCEPTED,
        ApplicationStatus.SIGNED,
        ApplicationStatus.ISSUED,
    ]

    for i, status in enumerate(path, start=1):
        application.transition_to(
            status, actor=ActorType.SYSTEM, actor_id=None, at=NOW + timedelta(minutes=i)
        )

    events = application.pull_events()
    assert [(e.from_status, e.to_status) for e in events] == list(
        zip([ApplicationStatus.DRAFT, *path[:-1]], path, strict=True)
    )
    assert application.status_changed_at == NOW + timedelta(minutes=len(path))
    assert not application.is_active


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (src, dst)
        for src in ApplicationStatus
        for dst in ApplicationStatus
        if dst not in TRANSITIONS[src]
    ],
)
def test_undocumented_transition_is_rejected(
    from_status: ApplicationStatus, to_status: ApplicationStatus
) -> None:
    application = make_draft()
    application.status = from_status
    application.pull_events()

    with pytest.raises(InvalidTransitionError):
        application.transition_to(
            to_status, actor=ActorType.SYSTEM, actor_id=None, at=NOW
        )
    assert application.status is from_status
    assert application.pull_events() == []


def test_submit_fixes_consent_time() -> None:
    application = make_draft()

    application.submit(actor_id=application.created_by, at=NOW)

    assert application.status is ApplicationStatus.SUBMITTED
    assert application.consent_at == NOW


def test_only_draft_can_be_edited() -> None:
    application = make_draft()
    application.submit(actor_id=application.created_by, at=NOW)

    with pytest.raises(ConflictError):
        application.update_draft(at=NOW, term_months=24)


def test_copy_only_after_decline_or_cancel() -> None:
    application = make_draft()
    with pytest.raises(ConflictError):
        application.copy_as_draft(created_by=uuid4(), at=NOW)

    application.transition_to(
        ApplicationStatus.CANCELLED, actor=ActorType.CLIENT, actor_id=None, at=NOW
    )
    copy = application.copy_as_draft(created_by=uuid4(), at=NOW)

    assert copy.id != application.id
    assert copy.status is ApplicationStatus.DRAFT
    assert (copy.product, copy.requested_amount, copy.term_months) == (
        application.product,
        application.requested_amount,
        application.term_months,
    )
