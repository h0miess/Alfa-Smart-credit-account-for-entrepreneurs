from pydantic import BaseModel, SecretStr


class S3Settings(BaseModel):
    ENDPOINT_URL: str = "http://localhost:9000"
    ACCESS_KEY: str = "minioadmin"
    SECRET_KEY: SecretStr = SecretStr("minioadmin")
    BUCKET: str = "credit-documents"
    REGION: str = "us-east-1"
