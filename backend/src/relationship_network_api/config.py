from typing import TYPE_CHECKING, ClassVar, cast, final

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from collections.abc import Callable


class DatabaseSettings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RN_",
        extra="ignore",
    )

    database_url: PostgresDsn = Field()


@final
class AppSettings(DatabaseSettings):
    redis_url: RedisDsn = RedisDsn("redis://127.0.0.1:16379/0")
    object_storage_endpoint: str = "127.0.0.1:9000"
    object_storage_access_key: SecretStr = Field()
    object_storage_secret_key: SecretStr = Field()
    object_storage_bucket: str = "relationship-network"
    object_storage_secure: bool = False
    session_ttl_seconds: int = 1209600
    session_renewal_window_seconds: int = 86400
    session_cookie_secure: bool = False
    invitation_ttl_seconds: int = 604800
    mfa_challenge_ttl_seconds: int = 300
    app_base_url: str = "http://localhost:3000"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "no-reply@relationship-network.local"
    smtp_use_tls: bool = True


def load_app_settings() -> AppSettings:
    settings_factory = cast("Callable[[], AppSettings]", AppSettings)
    return settings_factory()


def load_database_settings() -> DatabaseSettings:
    settings_factory = cast("Callable[[], DatabaseSettings]", DatabaseSettings)
    return settings_factory()


@final
class WorkerSettings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RN_",
        extra="ignore",
    )

    celery_broker_url: RedisDsn = RedisDsn("redis://127.0.0.1:16379/1")
    celery_result_backend: RedisDsn = RedisDsn("redis://127.0.0.1:16379/2")
