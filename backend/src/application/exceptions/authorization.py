from application.exceptions.base import ApplicationError


class AuthorizationError(ApplicationError):
    code = "unauthorized"

    def __init__(self) -> None:
        message = "Unauthorized"
        super().__init__(message)
