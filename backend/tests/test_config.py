from typing import Protocol, cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pydantic import ValidationError

from relationship_network_api.config import (
    AppSettings,
    load_app_settings,
    load_database_settings,
)


class AppSettingsWithoutEnvFile(Protocol):
    def __call__(self, *, _env_file: None) -> AppSettings: ...


def test_settings_require_deployment_secrets(monkeypatch: MonkeyPatch) -> None:
    for variable in (
        "RN_DATABASE_URL",
        "RN_OBJECT_STORAGE_ACCESS_KEY",
        "RN_OBJECT_STORAGE_SECRET_KEY",
    ):
        monkeypatch.delenv(variable, raising=False)

    settings_factory = cast("AppSettingsWithoutEnvFile", cast("object", AppSettings))
    with pytest.raises(ValidationError):
        _settings = settings_factory(_env_file=None)


def test_database_settings_do_not_require_unrelated_secrets(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(
        "RN_DATABASE_URL",
        "postgresql+asyncpg://app:password@postgres:5432/relationship_network",
    )

    settings = load_database_settings()

    assert str(settings.database_url).endswith("/relationship_network")


def test_session_settings_default_to_pinned_contract(monkeypatch: MonkeyPatch) -> None:
    # Given deployment configuration without session overrides
    monkeypatch.setenv(
        "RN_DATABASE_URL",
        "postgresql+asyncpg://app:password@postgres:5432/relationship_network",
    )
    monkeypatch.setenv("RN_OBJECT_STORAGE_ACCESS_KEY", "local-access")
    monkeypatch.setenv("RN_OBJECT_STORAGE_SECRET_KEY", "local-secret")
    for variable in (
        "RN_SESSION_TTL_SECONDS",
        "RN_SESSION_RENEWAL_WINDOW_SECONDS",
        "RN_SESSION_COOKIE_SECURE",
    ):
        monkeypatch.delenv(variable, raising=False)

    # When settings cross the application boundary
    settings = load_app_settings()

    # Then the session contract defaults to fourteen days with a one-day renewal window
    assert settings.session_ttl_seconds == 1209600
    assert settings.session_renewal_window_seconds == 86400
    assert not settings.session_cookie_secure


def test_session_settings_parse_environment_overrides(monkeypatch: MonkeyPatch) -> None:
    # Given session configuration injected through environment variables
    monkeypatch.setenv(
        "RN_DATABASE_URL",
        "postgresql+asyncpg://app:password@postgres:5432/relationship_network",
    )
    monkeypatch.setenv("RN_OBJECT_STORAGE_ACCESS_KEY", "local-access")
    monkeypatch.setenv("RN_OBJECT_STORAGE_SECRET_KEY", "local-secret")
    monkeypatch.setenv("RN_SESSION_TTL_SECONDS", "3600")
    monkeypatch.setenv("RN_SESSION_RENEWAL_WINDOW_SECONDS", "600")
    monkeypatch.setenv("RN_SESSION_COOKIE_SECURE", "true")

    # When settings cross the application boundary
    settings = load_app_settings()

    # Then the overrides are parsed into the runtime contract
    assert settings.session_ttl_seconds == 3600
    assert settings.session_renewal_window_seconds == 600
    assert settings.session_cookie_secure


def test_settings_parse_runtime_environment(monkeypatch: MonkeyPatch) -> None:
    # Given all deployment configuration is injected through environment variables
    monkeypatch.setenv(
        "RN_DATABASE_URL",
        "postgresql+asyncpg://app:password@postgres:5432/relationship_network",
    )
    monkeypatch.setenv("RN_REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("RN_OBJECT_STORAGE_ENDPOINT", "minio:9000")
    monkeypatch.setenv("RN_OBJECT_STORAGE_ACCESS_KEY", "local-access")
    monkeypatch.setenv("RN_OBJECT_STORAGE_SECRET_KEY", "local-secret")
    monkeypatch.setenv("RN_OBJECT_STORAGE_BUCKET", "relationship-network")

    # When settings cross the application boundary
    settings = load_app_settings()

    # Then values are parsed into the runtime contract without exposing the secret
    assert str(settings.database_url).endswith("/relationship_network")
    assert str(settings.redis_url) == "redis://redis:6379/0"
    assert settings.object_storage_endpoint == "minio:9000"
    assert settings.object_storage_secret_key.get_secret_value() == "local-secret"
    assert "local-secret" not in repr(settings)
