from domain.exceptions.base import AccessDeniedError, ConflictError
from domain.statuses import ApplicationStatus


class InvalidTransitionError(ConflictError):
    code = "invalid_transition"

    def __init__(self, from_status: ApplicationStatus, to_status: ApplicationStatus):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Переход заявки из статуса {from_status} в {to_status} недопустим"
        )


class SignerRequiredError(AccessDeniedError):
    code = "signer_required"

    def __init__(self) -> None:
        super().__init__(
            "Подписать договор может только руководитель компании: передайте заявку ему"
        )


class ContractMismatchError(ConflictError):
    code = "contract_mismatch"

    def __init__(self) -> None:
        super().__init__("Условия договора не совпадают с принятым предложением")


class OfferExpiredError(ConflictError):
    code = "offer_expired"

    def __init__(self) -> None:
        super().__init__("Срок действия предложения истёк")
