from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, model_validator

from domain.entities.user import UserRole


class Environment(StrEnum):
    DEV = "dev"
    PROD = "prod"
    LOCAL = "local"
    INTEGRATION_TEST = "integration_test"
    UNITTEST = "unittest"

    @property
    def is_local_environment(self) -> bool:
        return self in {
            Environment.LOCAL,
            Environment.INTEGRATION_TEST,
            Environment.UNITTEST,
        }


class AppSettings(BaseModel):
    ENVIRONMENT: Environment

    AUTH_ENABLED: bool = True

    MOCK_USER_UUID: UUID | None = None
    MOCK_USER_ROLE: UserRole = UserRole.CLIENT

    @model_validator(mode="after")
    def validate_auth_enabled(self) -> "AppSettings":
        if not self.AUTH_ENABLED and not self.ENVIRONMENT.is_local_environment:
            raise ValueError(
                f"AUTH_ENABLED=False недопустим в '{self.ENVIRONMENT}' окружении"
            )
        return self

    @model_validator(mode="after")
    def validate_mock_user_uuid(self) -> "AppSettings":
        if self.ENVIRONMENT.is_local_environment and self.MOCK_USER_UUID is None:
            raise ValueError(
                f"MOCK_USER_UUID обязателен в '{self.ENVIRONMENT}' окружении"
            )
        return self
