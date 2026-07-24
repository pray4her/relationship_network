import uuid
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TENANT_SETTING: Final = "app.tenant_id"
USER_SETTING: Final = "app.user_id"
INVITE_TOKEN_SETTING: Final = "app.invite_token_hash"  # noqa: S105


async def set_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Scope the current transaction to a tenant for row level security."""
    _ = await session.execute(
        text(f"SELECT set_config('{TENANT_SETTING}', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


async def set_user_context(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Scope the current transaction to a user for row level security."""
    _ = await session.execute(
        text(f"SELECT set_config('{USER_SETTING}', :user_id, true)"),
        {"user_id": str(user_id)},
    )


async def set_invitation_token_context(session: AsyncSession, token_hash: str) -> None:
    """Scope the current transaction to a single invitation token for row level security."""
    _ = await session.execute(
        text(f"SELECT set_config('{INVITE_TOKEN_SETTING}', :token_hash, true)"),
        {"token_hash": token_hash},
    )
