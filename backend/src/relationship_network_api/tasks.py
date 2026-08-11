import logging
import smtplib
import uuid
from email.message import EmailMessage
from typing import TYPE_CHECKING, Final, Literal, TypedDict, cast

import anyio
from sqlalchemy.exc import SQLAlchemyError

from relationship_network_api import tenant_context, usage_service
from relationship_network_api.celery_app import celery_app
from relationship_network_api.config import load_app_settings, load_database_settings
from relationship_network_api.db import create_engine_from_settings, create_session_factory
from relationship_network_api.llm_configuration_worker import (
    process_attempt,
    recover_expired_attempt_leases,
    run_scheduled_operation,
    schedule_due_attempts,
)

if TYPE_CHECKING:
    from celery import Task

logger = logging.getLogger(__name__)

SMOKE_TASK_NAME: Final = "relationship_network.smoke"
INVITATION_EMAIL_TASK_NAME: Final = "relationship_network.send_invitation_email"
RELEASE_EXPIRED_RESERVATIONS_TASK_NAME: Final = (
    "relationship_network.release_expired_usage_reservations"
)
EXPIRE_DUE_SUBSCRIPTIONS_TASK_NAME: Final = "relationship_network.expire_due_subscriptions"
PROCESS_LLM_CONFIGURATION_ATTEMPT_TASK_NAME: Final = (
    "relationship_network.process_llm_configuration_attempt"
)
SCHEDULE_DUE_LLM_CONFIGURATION_ATTEMPTS_TASK_NAME: Final = (
    "relationship_network.schedule_due_llm_configuration_attempts"
)
RECOVER_EXPIRED_LLM_CONFIGURATION_LEASES_TASK_NAME: Final = (
    "relationship_network.recover_expired_llm_configuration_leases"
)


class SmokeResult(TypedDict):
    request_id: str
    status: Literal["ok"]


def smoke_payload(request_id: str) -> SmokeResult:
    return SmokeResult(request_id=request_id, status="ok")


def send_invitation_email_payload(email: str, tenant_name: str, invite_url: str) -> None:
    """Deliver an invitation email, falling back to logging when SMTP is unconfigured."""
    settings = load_app_settings()
    if not settings.smtp_host:
        logger.info(
            "invitation email for %s to join %s: %s",
            email,
            tenant_name,
            invite_url,
        )
        return
    message = EmailMessage()
    message["Subject"] = f"邀请你加入 {tenant_name}"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                "你好，",  # noqa: RUF001
                "",
                f"你被邀请加入租户「{tenant_name}」。",
                "请点击以下链接接受邀请：",  # noqa: RUF001
                invite_url,
                "",
                "如果你不认识发件人，请忽略本邮件。",  # noqa: RUF001
            ]
        )
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            _ = smtp.starttls()
        if settings.smtp_username:
            password = (
                settings.smtp_password.get_secret_value()
                if settings.smtp_password is not None
                else ""
            )
            _ = smtp.login(settings.smtp_username, password)
        _ = smtp.send_message(message)


smoke = celery_app.task(name=SMOKE_TASK_NAME)(smoke_payload)
send_invitation_email = cast(
    "Task",
    celery_app.task(
        name=INVITATION_EMAIL_TASK_NAME,
        autoretry_for=(smtplib.SMTPException, OSError),
        retry_backoff=True,
        max_retries=3,
    )(send_invitation_email_payload),
)


def release_expired_usage_reservations_payload() -> int:
    """Release expired usage reservations across all tenants; returns the count."""
    return anyio.run(_release_expired_usage_reservations)


async def _release_expired_usage_reservations() -> int:
    settings = load_database_settings()
    engine = create_engine_from_settings(settings)
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            await tenant_context.set_platform_admin_context(session)
            return await usage_service.release_expired_reservations(session)
    finally:
        await engine.dispose()


release_expired_usage_reservations = cast(
    "Task",
    celery_app.task(
        name=RELEASE_EXPIRED_RESERVATIONS_TASK_NAME,
        autoretry_for=(SQLAlchemyError, OSError),
        retry_backoff=True,
        max_retries=3,
    )(release_expired_usage_reservations_payload),
)


def expire_due_subscriptions_payload() -> int:
    """Expire subscriptions past their billing period end; returns the count."""
    return anyio.run(_expire_due_subscriptions)


async def _expire_due_subscriptions() -> int:
    settings = load_database_settings()
    engine = create_engine_from_settings(settings)
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            await tenant_context.set_platform_admin_context(session)
            return await usage_service.expire_due_subscriptions(session)
    finally:
        await engine.dispose()


expire_due_subscriptions = cast(
    "Task",
    celery_app.task(
        name=EXPIRE_DUE_SUBSCRIPTIONS_TASK_NAME,
        autoretry_for=(SQLAlchemyError, OSError),
        retry_backoff=True,
        max_retries=3,
    )(expire_due_subscriptions_payload),
)


def process_llm_configuration_attempt_payload(attempt_id: str) -> None:
    """Run one idempotently claimed platform LLM configuration attempt."""
    anyio.run(process_attempt, uuid.UUID(attempt_id))


def schedule_due_llm_configuration_attempts_payload() -> int:
    """Move due retry plans back to queued and write fresh Outbox events."""
    return anyio.run(run_scheduled_operation, schedule_due_attempts)


def recover_expired_llm_configuration_leases_payload() -> int:
    """Recover expired platform attempt leases without creating new attempts."""
    return anyio.run(run_scheduled_operation, recover_expired_attempt_leases)


process_llm_configuration_attempt = cast(
    "Task",
    celery_app.task(
        name=PROCESS_LLM_CONFIGURATION_ATTEMPT_TASK_NAME,
        acks_late=True,
        reject_on_worker_lost=True,
    )(process_llm_configuration_attempt_payload),
)
schedule_due_llm_configuration_attempts = cast(
    "Task",
    celery_app.task(name=SCHEDULE_DUE_LLM_CONFIGURATION_ATTEMPTS_TASK_NAME)(
        schedule_due_llm_configuration_attempts_payload
    ),
)
recover_expired_llm_configuration_leases = cast(
    "Task",
    celery_app.task(name=RECOVER_EXPIRED_LLM_CONFIGURATION_LEASES_TASK_NAME)(
        recover_expired_llm_configuration_leases_payload
    ),
)
