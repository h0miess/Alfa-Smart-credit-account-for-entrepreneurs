from pydantic import BaseModel, SecretStr


class RedisSettings(BaseModel):
    HOST: str = "localhost"
    PORT: int = 6379
    DB: int = 0
    PASSWORD: SecretStr | None = None
    QUEUE_NAME: str = "credit-cabinet"

    @property
    def url(self) -> str:
        auth = f":{self.PASSWORD.get_secret_value()}@" if self.PASSWORD else ""
        return f"redis://{auth}{self.HOST}:{self.PORT}/{self.DB}"
