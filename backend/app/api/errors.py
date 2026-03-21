from __future__ import annotations

from typing import Any

from fastapi import HTTPException


_DEFAULT_ERROR_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    404: "NOT_FOUND",
    422: "UNPROCESSABLE_ENTITY",
    500: "INTERNAL_SERVER_ERROR",
}


def default_error_code(status_code: int) -> str:
    return _DEFAULT_ERROR_CODES.get(status_code, f"HTTP_{status_code}")


def api_error(
    *,
    status_code: int,
    detail: str,
    code: str | None = None,
    context: dict[str, Any] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "detail": detail,
            "code": code or default_error_code(status_code),
            "context": context or {},
        },
    )
