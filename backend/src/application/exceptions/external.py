from application.exceptions.base import ApplicationError


class ExternalServiceError(ApplicationError):
    code = "service_unavailable"

    def __init__(self, service: str, details: str) -> None:
        self.service = service
        self.details = details
        super().__init__(f"Сервис {service} временно недоступен")
