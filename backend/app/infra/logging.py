"""Logging configuration for the application."""

import contextvars
import json
import logging
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.infra.settings import get_settings

# Track if root logger has been configured
_configured = False
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


class RequestContextFilter(logging.Filter):
    """Attach context-local fields to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        for key, value in get_log_context().items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    """Format log records as one-line JSON for production log collection."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_FIELDS or key in payload or key == "request_id":
                continue
            if key.startswith("_"):
                continue
            payload[key] = _json_safe(value)

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

        if settings.log_format == "json":
            formatter: logging.Formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                fmt="%(asctime)s - %(levelname)s - [%(name)s] "
                "[request_id=%(request_id)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        handler.setFormatter(formatter)
        parent.handlers.clear()
        parent.addHandler(handler)
        parent.propagate = True

        # Reduce noise from third-party libraries
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
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
