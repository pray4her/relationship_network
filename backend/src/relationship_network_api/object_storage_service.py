"""Private MinIO/S3 object storage helpers for tenant documents."""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from typing import Final, final

from minio import Minio
from minio.error import MinioException
from urllib3 import PoolManager
from urllib3.util import Retry, Timeout

from relationship_network_api.config import AppSettings

DEFAULT_TIMEOUT_SECONDS: Final = 30


@final
class ObjectStorageError(Exception):
    """Raised when object storage cannot complete a put or get."""


@final
class ObjectStorage:
    """Thin wrapper around the MinIO client for private bucket operations."""

    def __init__(self, client: Minio, *, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    @property
    def bucket(self) -> str:
        return self._bucket

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        try:
            _ = self._client.put_object(
                self._bucket,
                key,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        except (MinioException, OSError) as error:
            raise ObjectStorageError from error

    def get_bytes(self, *, key: str) -> bytes:
        try:
            response = self._client.get_object(self._bucket, key)
        except (MinioException, OSError) as error:
            raise ObjectStorageError from error
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def stream_bytes(self, *, key: str) -> Iterator[bytes]:
        try:
            response = self._client.get_object(self._bucket, key)
        except (MinioException, OSError) as error:
            raise ObjectStorageError from error
        try:
            yield from response.stream(32 * 1024)
        finally:
            response.close()
            response.release_conn()


def build_object_storage(settings: AppSettings) -> ObjectStorage:
    """Build an ObjectStorage client from application settings."""
    client = Minio(
        endpoint=settings.object_storage_endpoint,
        access_key=settings.object_storage_access_key.get_secret_value(),
        secret_key=settings.object_storage_secret_key.get_secret_value(),
        secure=settings.object_storage_secure,
        http_client=PoolManager(
            timeout=Timeout(
                connect=DEFAULT_TIMEOUT_SECONDS,
                read=DEFAULT_TIMEOUT_SECONDS,
            ),
            retries=Retry(total=0),
        ),
    )
    return ObjectStorage(client, bucket=settings.object_storage_bucket)
