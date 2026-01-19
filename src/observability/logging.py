"""Structured logging configuration for Claude Fab Lab.

Provides JSON-formatted logs with context propagation for production use.
"""

import logging
import sys
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from contextvars import ContextVar
from functools import wraps

# Log level from environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # "json" or "text"

# Context variable for request-scoped data
_log_context: ContextVar[Dict[str, Any]] = ContextVar("log_context", default={})


class LogContext:
    """Context manager for adding context to logs."""

    def __init__(self, **kwargs):
        self.context = kwargs
        self._token = None

    def __enter__(self):
        current = _log_context.get().copy()
        current.update(self.context)
        self._token = _log_context.set(current)
        return self

    def __exit__(self, *args):
        if self._token:
            _log_context.reset(self._token)


def add_context(**kwargs):
    """Add context to current log scope."""
    current = _log_context.get().copy()
    current.update(kwargs)
    _log_context.set(current)


def clear_context():
    """Clear all log context."""
    _log_context.set({})


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context
        context = _log_context.get()
        if context:
            log_data["context"] = context

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message"
            ):
                log_data[key] = value

        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored text formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)

        # Format timestamp
        timestamp = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]

        # Build message
        msg = f"{color}{timestamp} [{record.levelname:8}]{self.RESET} "
        msg += f"\033[1m{record.name}\033[0m: {record.getMessage()}"

        # Add context
        context = _log_context.get()
        if context:
            context_str = " ".join(f"{k}={v}" for k, v in context.items())
            msg += f" \033[90m({context_str})\033[0m"

        # Add exception
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)

        return msg


def setup_logging(
    level: Optional[str] = None,
    format: Optional[str] = None
) -> None:
    """Set up logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Output format ("json" or "text")
    """
    level = level or LOG_LEVEL
    format = format or LOG_FORMAT

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level))

    # Set formatter
    if format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(ColoredFormatter())

    root_logger.addHandler(handler)

    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name (usually module path)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LoggedClass:
    """Mixin class that provides a logger."""

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(self.__class__.__module__ + "." + self.__class__.__name__)


def log_call(level: str = "DEBUG"):
    """Decorator to log function calls."""
    def decorator(func):
        logger = logging.getLogger(func.__module__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.log(
                getattr(logging, level),
                f"Calling {func.__name__}",
                extra={"args": str(args), "kwargs": str(kwargs)}
            )
            try:
                result = func(*args, **kwargs)
                logger.log(
                    getattr(logging, level),
                    f"{func.__name__} completed"
                )
                return result
            except Exception as e:
                logger.exception(f"{func.__name__} failed: {e}")
                raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger.log(
                getattr(logging, level),
                f"Calling {func.__name__}",
                extra={"args": str(args), "kwargs": str(kwargs)}
            )
            try:
                result = await func(*args, **kwargs)
                logger.log(
                    getattr(logging, level),
                    f"{func.__name__} completed"
                )
                return result
            except Exception as e:
                logger.exception(f"{func.__name__} failed: {e}")
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


# Initialize logging on module import
setup_logging()
