from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class ApplicationStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    CHECKING = "CHECKING"
    INFO_REQUESTED = "INFO_REQUESTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"
    SIGNED = "SIGNED"
    ISSUED = "ISSUED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"


_S = ApplicationStatus

TRANSITIONS: Final[Mapping[ApplicationStatus, frozenset[ApplicationStatus]]] = (
    MappingProxyType(
        {
            _S.DRAFT: frozenset({_S.SUBMITTED, _S.CANCELLED}),
            _S.SUBMITTED: frozenset({_S.CHECKING}),
            _S.CHECKING: frozenset(
                {_S.OFFERED, _S.INFO_REQUESTED, _S.MANUAL_REVIEW, _S.DECLINED}
            ),
            _S.MANUAL_REVIEW: frozenset({_S.OFFERED, _S.INFO_REQUESTED, _S.DECLINED}),
            _S.INFO_REQUESTED: frozenset({_S.CHECKING, _S.CANCELLED}),
            _S.OFFERED: frozenset({_S.ACCEPTED, _S.CANCELLED}),
            _S.ACCEPTED: frozenset({_S.SIGNED}),
            _S.SIGNED: frozenset({_S.ISSUED}),
            _S.ISSUED: frozenset(),
            _S.DECLINED: frozenset(),
            _S.CANCELLED: frozenset(),
        }
    )
)

TERMINAL_STATUSES: Final[frozenset[ApplicationStatus]] = frozenset(
    status for status, targets in TRANSITIONS.items() if not targets
)

PROCESSING_SLA: Final = timedelta(minutes=5)
INFO_REQUEST_TTL: Final = timedelta(days=30)
OFFER_TTL: Final = timedelta(days=14)


@dataclass(frozen=True, slots=True)
class StatusView:
    code: ApplicationStatus
    title: str
    next_action: str | None
    eta_text: str | None


STATUS_VIEW: Final[Mapping[ApplicationStatus, StatusView]] = MappingProxyType(
    {
        view.code: view
        for view in (
            StatusView(_S.DRAFT, "Черновик", "заполнить и отправить", None),
            StatusView(
                _S.SUBMITTED,
                "Заявка на рассмотрении",
                "ничего, обычно это занимает минуты",
                "Решение обычно за несколько минут",
            ),
            StatusView(
                _S.CHECKING,
                "Заявка на рассмотрении",
                "ничего, обычно это занимает минуты",
                "Решение обычно за несколько минут",
            ),
            StatusView(
                _S.INFO_REQUESTED,
                "Нужны документы",
                "загрузить документы из списка",
                "Ждём документы 30 дней, затем заявка будет отменена",
            ),
            StatusView(
                _S.MANUAL_REVIEW,
                "Заявку проверяет специалист",
                "ждать, ориентир — 1 рабочий день",
                "Ориентир — 1 рабочий день",
            ),
            StatusView(
                _S.OFFERED,
                "Готово предложение",
                "изучить условия и принять или отказаться",
                "Предложение действует 14 дней",
            ),
            StatusView(_S.ACCEPTED, "Условия приняты", "подписать договор", None),
            StatusView(
                _S.SIGNED,
                "Договор подписан",
                "ждать зачисления",
                "Зачисление обычно за несколько минут",
            ),
            StatusView(_S.ISSUED, "Деньги на счёте", None, None),
            StatusView(
                _S.DECLINED,
                "Отказ",
                "посмотреть причину; подать новую заявку на других условиях",
                None,
            ),
            StatusView(
                _S.CANCELLED,
                "Заявка отменена",
                "при необходимости подать новую",
                None,
            ),
        )
    }
)


def eta_deadline(
    status: ApplicationStatus,
    entered_at: datetime,
    offer_valid_until: date | None = None,
) -> datetime | None:
    match status:
        case _S.SUBMITTED | _S.CHECKING | _S.SIGNED:
            return entered_at + PROCESSING_SLA
        case _S.MANUAL_REVIEW:
            return add_business_days(entered_at, 1)
        case _S.INFO_REQUESTED:
            return entered_at + INFO_REQUEST_TTL
        case _S.OFFERED if offer_valid_until is not None:
            return datetime.combine(offer_valid_until, time.max, tzinfo=UTC)
    return None


def add_business_days(moment: datetime, days: int) -> datetime:
    result = moment
    while days > 0:
        result += timedelta(days=1)
        if result.weekday() < 5:
            days -= 1
    return result
