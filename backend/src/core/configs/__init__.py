from pydantic_settings import BaseSettings, SettingsConfigDict

from core.configs.app import AppSettings
from core.configs.auth import AuthSettings
from core.configs.database import PostgresSettings, SQLEngineSettings
from core.configs.redis import RedisSettings
from core.configs.seed import SeedSettings
from core.configs.services import MocksSettings, ScoringSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore",
    )
    app: AppSettings
    postgres: PostgresSettings
    sql_engine: SQLEngineSettings = SQLEngineSettings()
    auth: AuthSettings
    redis: RedisSettings = RedisSettings()
    seed: SeedSettings = SeedSettings()
    scoring: ScoringSettings = ScoringSettings()
    mocks: MocksSettings = MocksSettings()


settings = Settings()
