"""Logging configuration for the application."""

import logging
import sys

from app.infra.settings import get_settings

# Track if root logger has been configured
_configured = False


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

        # Console handler with colored output
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        # Format: timestamp - level - logger name - message
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(levelname)s - [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        parent.addHandler(handler)

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
