from typing import Final, final

from anyio import to_thread
from asyncpg import PostgresError
from minio import Minio
from minio.error import MinioException
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
from urllib3 import PoolManager, Retry, Timeout
from urllib3.exceptions import HTTPError

from relationship_network_api.config import AppSettings
from relationship_network_api.health import (
    DependencyCheck,
    DependencyName,
    DependencyProbeError,
    DependencyStatus,
)

PROBE_TIMEOUT_SECONDS: Final = 2.0


@final
class PostgresDependencyCheck:
    name: DependencyName = "postgres"

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def check(self) -> DependencyStatus:
        engine = create_async_engine(
            self._database_url,
            connect_args={
                "command_timeout": PROBE_TIMEOUT_SECONDS,
                "timeout": PROBE_TIMEOUT_SECONDS,
            },
            pool_pre_ping=True,
        )
        try:
            async with engine.connect() as connection:
                _result = await connection.execute(text("SELECT 1"))
        except (OSError, PostgresError, SQLAlchemyError) as error:
            raise DependencyProbeError from error
        finally:
            await engine.dispose()
        return DependencyStatus(name="postgres", status="ok")


@final
class RedisDependencyCheck:
    name: DependencyName = "redis"

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    async def check(self) -> DependencyStatus:
        try:
            async with Redis.from_url(
                self._redis_url,
                socket_connect_timeout=PROBE_TIMEOUT_SECONDS,
                socket_timeout=PROBE_TIMEOUT_SECONDS,
            ) as client:
                await client.ping()
        except (OSError, RedisError) as error:
            raise DependencyProbeError from error
        return DependencyStatus(name="redis", status="ok")


@final
class ObjectStorageDependencyCheck:
    name: DependencyName = "object_storage"

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
    ) -> None:
        self._bucket = bucket
        self._client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            http_client=PoolManager(
                timeout=Timeout(
                    connect=PROBE_TIMEOUT_SECONDS,
                    read=PROBE_TIMEOUT_SECONDS,
                ),
                retries=Retry(total=0),
            ),
        )

    async def check(self) -> DependencyStatus:
        try:
            bucket_exists = await to_thread.run_sync(
                self._client.bucket_exists,
                self._bucket,
            )
        except (HTTPError, MinioException, OSError) as error:
            raise DependencyProbeError from error
        return DependencyStatus(
            name="object_storage",
            status="ok" if bucket_exists else "unavailable",
        )


def build_dependency_checks(settings: AppSettings) -> tuple[DependencyCheck, ...]:
    return (
        PostgresDependencyCheck(str(settings.database_url)),
        RedisDependencyCheck(str(settings.redis_url)),
        ObjectStorageDependencyCheck(
            endpoint=settings.object_storage_endpoint,
            access_key=settings.object_storage_access_key.get_secret_value(),
            secret_key=settings.object_storage_secret_key.get_secret_value(),
            bucket=settings.object_storage_bucket,
            secure=settings.object_storage_secure,
        ),
    )
