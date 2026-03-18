from __future__ import annotations


class UpstreamApiUnavailableError(RuntimeError):
    """Raised when the configured model provider is unavailable.

    This is intentionally broader than a single HTTP status. It covers
    rate limiting, exhausted quota, transient upstream failures, and
    connectivity failures where continuing the simulation would produce
    synthetic fallback data instead of model-backed behavior.
    """


def is_upstream_api_unavailable_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    if not message:
        return False

    markers = (
        "rate_limit_error",
        "usage limit exceeded",
        "quota",
        "too many requests",
        "429",
        "connection failed",
        "connection error",
        "server closed the connection unexpectedly",
        "timed out",
        "timeout",
        "service unavailable",
        "temporarily unavailable",
        "overloaded",
        "api unavailable",
    )
    return any(marker in message for marker in markers)
