from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    SEED_FILE: Path = Path("../seed/companies.json")
    TIMEOUT_DELAY_IN_SECONDS: float = 30


settings = Settings()
