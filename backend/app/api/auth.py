from __future__ import annotations

from secrets import compare_digest

from fastapi import Header, status

from app.api.errors import api_error
from app.infra.settings import get_settings

DEMO_ADMIN_HEADER = "x-demo-admin-password"


def is_demo_write_protected() -> bool:
    return bool(get_settings().demo_admin_password)


def has_demo_admin_access(password: str | None) -> bool:
    configured_password = get_settings().demo_admin_password
    if not configured_password:
        return True
    if not password:
        return False
    return compare_digest(password, configured_password)


async def require_demo_admin_access(
    demo_admin_password: str | None = Header(default=None, alias=DEMO_ADMIN_HEADER),
) -> None:
    if has_demo_admin_access(demo_admin_password):
        return
    raise api_error(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin access required for write operations",
        code="DEMO_ADMIN_ACCESS_REQUIRED",
    )
