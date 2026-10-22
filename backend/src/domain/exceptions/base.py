class CreditCabinetException(Exception):
    code: str | None = None


class DomainError(CreditCabinetException):
    pass


class AccessDeniedError(DomainError):
    code = "forbidden"

    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message)
