from collections.abc import Iterator

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from core.configs.s3 import S3Settings
from infra.s3.storage import S3DocumentStorage

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def minio_url() -> Iterator[str]:
    container = (
        DockerContainer("pgsty/minio:RELEASE.2026-08-04T00-00-00Z")
        .with_command("server /data")
        .with_env("MINIO_ROOT_USER", "minioadmin")
        .with_env("MINIO_ROOT_PASSWORD", "minioadmin")
        .with_exposed_ports(9000)
        .waiting_for(LogMessageWaitStrategy("API:"))
    )
    with container:
        host = container.get_container_host_ip()
        yield f"http://{host}:{container.get_exposed_port(9000)}"


async def test_put_and_get_roundtrip(minio_url: str) -> None:
    storage = S3DocumentStorage(S3Settings(ENDPOINT_URL=minio_url, BUCKET="test-docs"))

    await storage.put("applications/1/doc", b"%PDF-1.4", "application/pdf")

    assert await storage.get("applications/1/doc") == b"%PDF-1.4"
