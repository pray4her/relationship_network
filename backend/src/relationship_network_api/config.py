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
    platform_admin_emails: str = ""
    invitation_ttl_seconds: int = 604800
    mfa_challenge_ttl_seconds: int = 300
    app_base_url: str = "http://localhost:3000"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "no-reply@relationship-network.local"
    smtp_use_tls: bool = True
    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = ""
    openrouter_site_name: str = "Relationship Network"
    llm_raw_response_keys: SecretStr = SecretStr("{}")
    llm_raw_response_active_key_id: str = ""


def load_app_settings() -> AppSettings:
    settings_factory = cast("Callable[[], AppSettings]", AppSettings)
    return settings_factory()


def parse_platform_admin_emails(raw: str) -> frozenset[str]:
    """Parse the comma-separated platform admin email allowlist from settings."""
    return frozenset(entry.strip().lower() for entry in raw.split(",") if entry.strip())


def load_database_settings() -> DatabaseSettings:
    settings_factory = cast("Callable[[], DatabaseSettings]", DatabaseSettings)
    return settings_factory()


@final
class PlatformLlmSettings(DatabaseSettings):
    """Database and OpenRouter settings required by the restricted platform Worker."""

    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = ""
    openrouter_site_name: str = "Relationship Network"
    llm_raw_response_keys: SecretStr = SecretStr("{}")
    llm_raw_response_active_key_id: str = ""


def load_platform_llm_settings() -> PlatformLlmSettings:
    settings_factory = cast("Callable[[], PlatformLlmSettings]", PlatformLlmSettings)
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
