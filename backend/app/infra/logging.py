"""Logging configuration for the application."""

import logging
import sys
from functools import lru_cache

from app.infra.settings import get_settings


@lru_cache(maxsize=1)
def get_logger(name: str = "trumanworld") -> logging.Logger:
    """Get configured logger instance."""
    settings = get_settings()
    
    # Create logger
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Set level from settings
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Console handler with colored output
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Format: timestamp - level - logger name - message
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    return logger


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
