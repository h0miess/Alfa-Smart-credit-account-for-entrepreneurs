class CreditCabinetException(Exception):
    code: str | None = None


class DomainError(CreditCabinetException):
    pass


class AccessDeniedError(DomainError):
    code = "forbidden"

    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message)


class NotFoundError(DomainError):
    code = "not_found"

    def __init__(self, message: str = "Не найдено") -> None:
        super().__init__(message)


class ConflictError(DomainError):
    code = "conflict"


class BusinessRuleViolationError(DomainError):
    code = "business_rule_violation"
