from pydantic import BaseModel


class ScoringSettings(BaseModel):
    URL: str = "http://localhost:8001"
    TIMEOUT_IN_SECONDS: float = 5
    ATTEMPTS: int = 3
    CATALOG_TTL_IN_SECONDS: int = 300


class MocksSettings(BaseModel):
    URL: str = "http://localhost:8002"
    TIMEOUT_IN_SECONDS: float = 5
    ATTEMPTS: int = 3
