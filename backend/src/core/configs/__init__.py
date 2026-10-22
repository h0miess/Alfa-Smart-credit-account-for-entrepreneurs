from pydantic_settings import BaseSettings, SettingsConfigDict

from core.configs.database import PostgresSettings, SQLEngineSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore",
    )
    postgres: PostgresSettings
    sql_engine: SQLEngineSettings = SQLEngineSettings()


settings = Settings()
