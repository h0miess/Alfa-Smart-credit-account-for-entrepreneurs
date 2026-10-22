from pydantic import BaseModel, SecretStr
from sqlalchemy import URL


class PostgresSettings(BaseModel):
    HOST: str = "localhost"
    PORT: int = 5432
    DB: str
    USER: str
    PASSWORD: SecretStr

    @property
    def url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.USER,
            password=self.PASSWORD.get_secret_value(),
            host=self.HOST,
            port=self.PORT,
            database=self.DB,
        )


class SQLEngineSettings(BaseModel):
    ECHO: bool = False
    ECHO_POOL: bool = False
    POOL_SIZE: int = 5
    MAX_OVERFLOW: int = 10
