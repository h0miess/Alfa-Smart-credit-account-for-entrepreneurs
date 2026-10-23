import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError

from application.exceptions.external import ExternalServiceError
from application.interfaces.storage import DocumentStorage
from core.configs.s3 import S3Settings

logger = logging.getLogger("credit_cabinet.storage")

SERVICE_NAME = "хранилища документов"


class S3DocumentStorage(DocumentStorage):
    def __init__(self, settings: S3Settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session()
        self._bucket_ready = False

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        async with self._client() as s3:
            await self._ensure_bucket(s3)
            await s3.put_object(
                Bucket=self._settings.BUCKET,
                Key=key,
                Body=data,
                ContentType=content_type,
            )

    async def get(self, key: str) -> bytes:
        async with self._client() as s3:
            response = await s3.get_object(Bucket=self._settings.BUCKET, Key=key)
            async with response["Body"] as body:
                data: bytes = await body.read()
                return data

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[Any]:
        try:
            async with self._session.client(
                "s3",
                endpoint_url=self._settings.ENDPOINT_URL,
                aws_access_key_id=self._settings.ACCESS_KEY,
                aws_secret_access_key=self._settings.SECRET_KEY.get_secret_value(),
                region_name=self._settings.REGION,
            ) as s3:
                yield s3
        except (BotoCoreError, ClientError) as e:
            logger.error("Ошибка хранилища документов: %r", e)
            raise ExternalServiceError(SERVICE_NAME, repr(e)) from e

    async def _ensure_bucket(self, s3: Any) -> None:
        if self._bucket_ready:
            return
        try:
            await s3.head_bucket(Bucket=self._settings.BUCKET)
        except ClientError:
            await s3.create_bucket(Bucket=self._settings.BUCKET)
        self._bucket_ready = True
