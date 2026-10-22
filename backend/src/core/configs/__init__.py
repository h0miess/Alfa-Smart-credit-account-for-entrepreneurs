from pydantic_settings import BaseSettings, SettingsConfigDict

from core.configs.app import AppSettings
from core.configs.auth import AuthSettings
from core.configs.database import PostgresSettings, SQLEngineSettings


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


settings = Settings()
