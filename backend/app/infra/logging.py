"""Logging configuration for the application."""

import asyncio
import contextvars
import json
import logging
import re
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.infra.settings import get_settings

# Track if root logger has been configured
_configured = False
LOG_SCHEMA_VERSION = 1
SERVICE_NAME = "trumanworld-backend"
REDACTED = "[REDACTED]"
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trumanworld_request_id",
    default=None,
)
_log_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "trumanworld_log_context",
    default=None,
)

_STANDARD_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "database_url",
    "password",
    "passwd",
    "redis_url",
    "secret",
    "token",
)
_SENSITIVE_PATTERNS = (
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*"), rf"\1{REDACTED}"),
    (re.compile(r"\b(?:sk|gsk|xai)-[A-Za-z0-9_-]{8,}\b", re.IGNORECASE), REDACTED),
    (
        re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://[^:/\s]+:)[^@\s]+(@)"),
        rf"\1{REDACTED}\2",
    ),
    (
        re.compile(
            r"(?i)((?:api[_-]?key|authorization|password|passwd|secret|token)\s*[=:]\s*)"
            r"[^\s,;&]+"
        ),
        rf"\1{REDACTED}",
    ),
)


def set_request_id(request_id: str | None) -> contextvars.Token[str | None]:
    """Set request id for log records in the current context."""
    return _request_id.set(request_id)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    """Reset request id context after request handling."""
    _request_id.reset(token)


def get_request_id() -> str | None:
    """Return current request id from context."""
    return _request_id.get()


def bind_log_context(**fields: Any) -> contextvars.Token[dict[str, Any] | None]:
    """Bind structured fields to all log records in the current context."""
    current = _log_context.get() or {}
    merged = {**current, **{key: value for key, value in fields.items() if value is not None}}
    return _log_context.set(merged)


def reset_log_context(token: contextvars.Token[dict[str, Any] | None]) -> None:
    """Reset structured log context."""
    _log_context.reset(token)


def get_log_context() -> Mapping[str, Any]:
    """Return structured log context for the current execution context."""
    return _log_context.get() or {}


def create_background_task(coro, *, name: str | None = None) -> asyncio.Task:
    """Create a task without leaking HTTP or operation context into its lifetime."""
    context = contextvars.copy_context()
    context.run(_request_id.set, None)
    context.run(_log_context.set, None)
    return asyncio.create_task(coro, name=name, context=context)


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def redact_log_value(value: Any, *, key: object | None = None) -> Any:
    """Return a JSON-safe value with credentials removed recursively."""
    if key is not None and _is_sensitive_key(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_log_value(item, key=item_key) for item_key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact_log_value(item) for item in value)
    if isinstance(value, list):
        return [redact_log_value(item) for item in value]
    if isinstance(value, str):
        sanitized = value
        for pattern, replacement in _SENSITIVE_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized
    return value


class RedactionFilter(logging.Filter):
    """Prevent secrets from reaching text or JSON handlers."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_log_value(record.msg)
        if isinstance(record.args, Mapping):
            record.args = redact_log_value(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(redact_log_value(item) for item in record.args)
        for key, value in tuple(record.__dict__.items()):
            if key not in _STANDARD_LOG_RECORD_FIELDS:
                setattr(record, key, redact_log_value(value, key=key))
        return True


class RequestContextFilter(logging.Filter):
    """Attach context-local fields to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        for key, value in get_log_context().items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class RedactingTextFormatter(logging.Formatter):
    """Apply the same secret policy to text exceptions and stack traces."""

    def formatException(self, exc_info) -> str:  # noqa: N802 - logging API name
        return redact_log_value(super().formatException(exc_info))

    def formatStack(self, stack_info: str) -> str:  # noqa: N802 - logging API name
        return redact_log_value(super().formatStack(stack_info))


class JsonFormatter(logging.Formatter):
    """Format log records as one-line JSON for production log collection."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "schema_version": LOG_SCHEMA_VERSION,
            "service": SERVICE_NAME,
            "environment": get_settings().app_env,
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_log_value(record.getMessage()),
        }

        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id

        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
            payload["exception"] = redact_log_value(self.formatException(record.exc_info))
        if record.stack_info:
            payload["stack"] = redact_log_value(self.formatStack(record.stack_info))

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_FIELDS or key in payload or key == "request_id":
                continue
            if key.startswith("_"):
                continue
            payload[key] = _json_safe(redact_log_value(value, key=key))

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def get_logger(name: str = "trumanworld") -> logging.Logger:
    """Get configured logger instance.

    All loggers under 'trumanworld' hierarchy inherit the same configuration.
    """
    global _configured
    settings = get_settings()

    # Configure the root trumanworld logger once
    if not _configured:
        _configured = True
        level = getattr(logging, settings.log_level.upper(), logging.INFO)

        # Configure the parent logger
        parent = logging.getLogger("trumanworld")
        parent.setLevel(level)

        # Console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.addFilter(RequestContextFilter())
        handler.addFilter(RedactionFilter())

        if settings.log_format == "json":
            formatter: logging.Formatter = JsonFormatter()
        else:
            formatter = RedactingTextFormatter(
                fmt="%(asctime)s - %(levelname)s - [%(name)s] "
                "[request_id=%(request_id)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        handler.setFormatter(formatter)
        parent.handlers.clear()
        parent.addHandler(handler)
        parent.propagate = False

        # Keep framework errors in the same stream/schema. Application middleware
        # owns access logs so uvicorn.access remains suppressed to avoid duplicates.
        for logger_name in ("uvicorn", "uvicorn.error"):
            external_logger = logging.getLogger(logger_name)
            external_logger.handlers.clear()
            external_logger.addHandler(handler)
            external_logger.setLevel(level)
            external_logger.propagate = False
        access_logger = logging.getLogger("uvicorn.access")
        access_logger.handlers.clear()
        access_logger.addHandler(handler)
        access_logger.setLevel(logging.WARNING)
        access_logger.propagate = False
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Return the requested logger (under trumanworld hierarchy if not already)
    if name.startswith("trumanworld"):
        return logging.getLogger(name)
    elif name.startswith("app"):
        # Convert app.xxx to trumanworld.app.xxx for consistent hierarchy
        return logging.getLogger(f"trumanworld.{name}")
    else:
        return logging.getLogger(f"trumanworld.{name}")


# Convenience function for quick logging
def debug(msg: str, *args, **kwargs):
    """Log debug message."""
    get_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """Log info message."""
    get_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """Log warning message."""
    get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """Log error message."""
    get_logger().error(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs):
    """Log exception with traceback."""
    get_logger().exception(msg, *args, **kwargs)
