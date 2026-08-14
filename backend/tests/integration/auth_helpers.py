"""Shared registration and MFA helpers for integration tests."""

from datetime import UTC, datetime
from typing import cast

from httpx import AsyncClient

from relationship_network_api.security import totp_code

PASSWORD = "integration-secret-1"


async def register(
    client: AsyncClient,
    *,
    email: str,
    invite_token: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": email,
        "password": PASSWORD,
        "display_name": "集成用户",
        "tenant_name": None,
    }
    if invite_token is not None:
        payload["invite_token"] = invite_token
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201
    return cast("dict[str, object]", response.json())


def current_code(secret: str) -> str:
    return totp_code(secret, at_time=int(datetime.now(UTC).timestamp()))


async def enable_mfa(client: AsyncClient) -> tuple[str, list[str]]:
    """Run setup + enable; returns the TOTP secret and recovery codes."""
    setup = await client.post("/auth/mfa/setup")
    assert setup.status_code == 200
    secret = cast("str", setup.json()["secret"])
    enabled = await client.post("/auth/mfa/enable", json={"code": current_code(secret)})
    assert enabled.status_code == 200
    codes = cast("list[str]", enabled.json()["recovery_codes"])
    assert len(codes) == 10
    return secret, codes


async def login_pending(client: AsyncClient, *, email: str) -> str:
    """Login against an MFA account; returns the raw challenge token."""
    login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    body = login.json()
    assert body["mfa_required"] is True
    assert "rn_session" not in login.headers.get("set-cookie", "")
    return cast("str", body["mfa_token"])
