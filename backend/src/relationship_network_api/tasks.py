import logging
import smtplib
from email.message import EmailMessage
from typing import TYPE_CHECKING, Final, Literal, TypedDict, cast

from relationship_network_api.celery_app import celery_app
from relationship_network_api.config import load_app_settings

if TYPE_CHECKING:
    from celery import Task

logger = logging.getLogger(__name__)

SMOKE_TASK_NAME: Final = "relationship_network.smoke"
INVITATION_EMAIL_TASK_NAME: Final = "relationship_network.send_invitation_email"


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
