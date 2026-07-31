import logging
import smtplib
from email.message import EmailMessage
from types import SimpleNamespace
from typing import Protocol, Self, cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy.exc import SQLAlchemyError

from relationship_network_api import tasks
from relationship_network_api.config import AppSettings
from relationship_network_api.tasks import (
    INVITATION_EMAIL_TASK_NAME,
    RELEASE_EXPIRED_RESERVATIONS_TASK_NAME,
    SMOKE_TASK_NAME,
    release_expired_usage_reservations,
    release_expired_usage_reservations_payload,
    send_invitation_email,
    send_invitation_email_payload,
    smoke_payload,
)


def test_smoke_task_returns_correlated_success() -> None:
    # Given a caller-provided correlation identifier
    request_id = "smoke-test-001"

    # When the worker executes the public smoke task
    result = smoke_payload(request_id)

    # Then the result proves the same task instance completed
    assert result == {"request_id": request_id, "status": "ok"}
    assert SMOKE_TASK_NAME == "relationship_network.smoke"


def make_settings(**overrides: object) -> AppSettings:
    values: dict[str, object] = {
        "smtp_host": None,
        "smtp_port": 587,
        "smtp_username": None,
        "smtp_password": None,
        "smtp_from": "no-reply@relationship-network.local",
        "smtp_use_tls": True,
    }
    values.update(overrides)
    return cast("AppSettings", cast("object", SimpleNamespace(**values)))


def test_invitation_email_logs_url_when_smtp_unconfigured(
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Given no SMTP host configured (development mode)
    monkeypatch.setattr(tasks, "load_app_settings", make_settings)

    # When the invitation email task runs
    with caplog.at_level(logging.INFO, logger="relationship_network_api.tasks"):
        send_invitation_email_payload(
            "invitee@example.com",
            "Acme 科技",
            "http://localhost:3000/invite/raw-token",
        )

    # Then the invite URL is logged instead of sent
    assert "http://localhost:3000/invite/raw-token" in caplog.text
    assert INVITATION_EMAIL_TASK_NAME == "relationship_network.send_invitation_email"


def test_invitation_email_sends_via_smtp_when_configured(monkeypatch: MonkeyPatch) -> None:
    # Given a configured SMTP relay and a spy on the SMTP client
    sent: list[EmailMessage] = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, *, timeout: int) -> None:
            assert (host, port, timeout) == ("smtp.example.com", 2525, 10)

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def starttls(self) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            assert username == "mailer@example.com"
            assert password == "secret-password"

        def send_message(self, message: EmailMessage) -> None:
            sent.append(message)

    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    monkeypatch.setattr(
        tasks,
        "load_app_settings",
        lambda: make_settings(
            smtp_host="smtp.example.com",
            smtp_port=2525,
            smtp_username="mailer@example.com",
            smtp_password=SimpleNamespace(get_secret_value=lambda: "secret-password"),
        ),
    )

    # When the invitation email task runs
    send_invitation_email_payload(
        "invitee@example.com",
        "Acme 科技",
        "http://localhost:3000/invite/raw-token",
    )

    # Then a plain-text Chinese invitation email is sent
    assert len(sent) == 1
    message = sent[0]
    assert message["To"] == "invitee@example.com"
    subject = message["Subject"]
    assert subject is not None
    assert "Acme 科技" in subject
    assert "http://localhost:3000/invite/raw-token" in message.get_content()


class _RetryPolicy(Protocol):
    autoretry_for: tuple[type[BaseException], ...]
    retry_backoff: bool
    max_retries: int


def test_invitation_email_retries_smtp_failures_with_backoff() -> None:
    # Given the registered invitation email task (attributes missing from celery stubs)
    task = cast("_RetryPolicy", cast("object", send_invitation_email))

    # Then transient SMTP and network failures retry with exponential backoff
    assert smtplib.SMTPException in task.autoretry_for
    assert OSError in task.autoretry_for
    assert task.retry_backoff is True
    assert task.max_retries == 3


def test_invitation_email_logs_url_when_smtp_host_empty(
    monkeypatch: MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Given an empty SMTP host (compose default without SMTP configured)
    monkeypatch.setattr(tasks, "load_app_settings", lambda: make_settings(smtp_host=""))

    # When the invitation email task runs
    with caplog.at_level(logging.INFO, logger="relationship_network_api.tasks"):
        send_invitation_email_payload(
            "invitee@example.com",
            "Acme 科技",
            "http://localhost:3000/invite/raw-token",
        )

    # Then the invite URL is logged instead of sent
    assert "http://localhost:3000/invite/raw-token" in caplog.text


def test_release_expired_reservations_payload_runs_db_sweep(monkeypatch: MonkeyPatch) -> None:
    # Given the database-running sweep stubbed out
    async def fake_sweep() -> int:
        return 7

    monkeypatch.setattr(tasks, "_release_expired_usage_reservations", fake_sweep)

    # When the worker payload runs
    released = release_expired_usage_reservations_payload()

    # Then the sweep result is returned
    assert released == 7
    assert RELEASE_EXPIRED_RESERVATIONS_TASK_NAME == (
        "relationship_network.release_expired_usage_reservations"
    )


def test_release_expired_reservations_retries_db_failures_with_backoff() -> None:
    # Given the registered sweeper task (attributes missing from celery stubs)
    task = cast("_RetryPolicy", cast("object", release_expired_usage_reservations))

    # Then transient database and network failures retry with exponential backoff
    assert SQLAlchemyError in task.autoretry_for
    assert OSError in task.autoretry_for
    assert task.retry_backoff is True
    assert task.max_retries == 3
