#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Provide structured logging helpers for refactor-safe observability."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Literal

_BASE_LOGGER_NAME = "sugarsubstitute"
_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_LOGGING_CONFIGURED = False
_FILE_LOG_PATHS: set[Path] = set()
_PROMPT_OBSERVABILITY_FILE_PATHS: set[Path] = set()
_PROMPT_OBSERVABILITY_LOGGER_PREFIXES = (
    f"{_BASE_LOGGER_NAME}.application.prompt_editor",
    f"{_BASE_LOGGER_NAME}.presentation.editor.prompt_editor",
)
_REDACTED = "[REDACTED]"
_SAFE_SENSITIVE_FRAGMENT_KEYS = frozenset({"token_count"})
_SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "session",
)
Clock = Callable[[], float]
LogLevel = Literal["debug", "info", "warning", "error"]


class _LoggerNamePrefixFilter(logging.Filter):
    """Allow records whose logger name belongs to one of the configured prefixes."""

    def __init__(self, prefixes: tuple[str, ...]) -> None:
        """Store logger name prefixes accepted by this filter."""

        super().__init__()
        self._prefixes = prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        """Return whether a log record should reach the filtered handler."""

        return any(
            record.name == prefix or record.name.startswith(f"{prefix}.")
            for prefix in self._prefixes
        )


def configure_default_logging(level: int = logging.WARNING) -> None:
    """Initialize process-wide logging without enabling verbose INFO chatter."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return
    logging.basicConfig(level=level, format=_DEFAULT_FORMAT)
    _LOGGING_CONFIGURED = True


def configure_file_logging(
    logs_dir: Path,
    *,
    level: int = logging.WARNING,
    filename: str = "sugarsubstitute.log",
) -> Path:
    """Attach a rotating durable warning/error log file for GUI diagnostics."""

    configure_default_logging(level=level)
    resolved_dir = logs_dir.resolve()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    log_path = resolved_dir / filename
    resolved_path = log_path.resolve()
    if resolved_path in _FILE_LOG_PATHS:
        return resolved_path

    handler = RotatingFileHandler(
        resolved_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(min(logging.getLogger().level or level, level))
    _FILE_LOG_PATHS.add(resolved_path)
    return resolved_path


def configure_prompt_observability_logging(
    logs_dir: Path,
    *,
    level: int = logging.DEBUG,
    filename: str = "prompt-editor-observability.log",
) -> Path:
    """Attach durable prompt-editor diagnostics without enabling global debug logging."""

    configure_default_logging()
    resolved_dir = logs_dir.resolve()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    log_path = resolved_dir / filename
    resolved_path = log_path.resolve()
    if resolved_path not in _PROMPT_OBSERVABILITY_FILE_PATHS:
        handler = RotatingFileHandler(
            resolved_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        handler.addFilter(
            _LoggerNamePrefixFilter(_PROMPT_OBSERVABILITY_LOGGER_PREFIXES)
        )
        logging.getLogger(_BASE_LOGGER_NAME).addHandler(handler)
        _PROMPT_OBSERVABILITY_FILE_PATHS.add(resolved_path)

    for logger_name in _PROMPT_OBSERVABILITY_LOGGER_PREFIXES:
        prefix_logger = logging.getLogger(logger_name)
        prefix_logger.setLevel(min(prefix_logger.level or level, level))

    return resolved_path


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced project logger."""
    configure_default_logging()
    child_name = f"{_BASE_LOGGER_NAME}.{name}" if name else _BASE_LOGGER_NAME
    return logging.getLogger(child_name)


def _serialize_context(context: dict[str, Any]) -> str:
    """Serialize context values into a compact key/value suffix."""
    if not context:
        return ""
    segments: list[str] = []
    for key, value in sorted(context.items()):
        normalized_key = key.strip().lower().replace("-", "_")
        serialized_value = _REDACTED
        if normalized_key in _SAFE_SENSITIVE_FRAGMENT_KEYS or not any(
            fragment in normalized_key for fragment in _SENSITIVE_KEY_FRAGMENTS
        ):
            serialized_value = str(value)
        segments.append(f"{key}={serialized_value}")
    return " | " + " ".join(segments)


def log_debug(logger: logging.Logger, message: str, **context: Any) -> None:
    """Log debug message with optional structured context."""
    if hasattr(logger, "isEnabledFor") and not logger.isEnabledFor(logging.DEBUG):
        return
    logger.debug(f"{message}{_serialize_context(context)}")


def log_info(logger: logging.Logger, message: str, **context: Any) -> None:
    """Log info message with optional structured context."""
    logger.info(f"{message}{_serialize_context(context)}")


def log_warning(logger: logging.Logger, message: str, **context: Any) -> None:
    """Log warning message with optional structured context."""
    logger.warning(f"{message}{_serialize_context(context)}")


def log_warning_exception(
    logger: logging.Logger,
    message: str,
    *,
    error: BaseException,
    **context: Any,
) -> None:
    """Log warning traceback context without serializing exception text."""

    safe_context = dict(context)
    safe_context["error_type"] = type(error).__name__
    logged_error = _LoggedException(type(error).__name__).with_traceback(
        error.__traceback__
    )
    logger.warning(
        f"{message}{_serialize_context(safe_context)}",
        exc_info=(type(logged_error), logged_error, error.__traceback__),
    )


def log_error(logger: logging.Logger, message: str, **context: Any) -> None:
    """Log error message with optional structured context."""
    logger.error(f"{message}{_serialize_context(context)}")


def log_exception(logger: logging.Logger, message: str, **context: Any) -> None:
    """Log exception details with context while preserving stack trace."""
    logger.exception(f"{message}{_serialize_context(context)}")


class _LoggedException(RuntimeError):
    """Represent the original exception type without exposing its message."""


def elapsed_ms_since(
    started_at: float,
    *,
    clock: Clock = time.perf_counter,
) -> float:
    """Return non-negative elapsed milliseconds from one monotonic start value."""

    return max(0.0, (clock() - started_at) * 1000.0)


def log_timing(
    logger: logging.Logger,
    message: str,
    *,
    started_at: float,
    level: LogLevel = "info",
    clock: Clock = time.perf_counter,
    **context: Any,
) -> float:
    """Log one elapsed timing measurement with structured context."""

    elapsed_ms = elapsed_ms_since(started_at, clock=clock)
    timing_context = dict(context)
    timing_context["elapsed_ms"] = f"{elapsed_ms:.3f}"
    if level == "debug":
        log_debug(logger, message, **timing_context)
    elif level == "warning":
        log_warning(logger, message, **timing_context)
    elif level == "error":
        log_error(logger, message, **timing_context)
    else:
        log_info(logger, message, **timing_context)
    return elapsed_ms


__all__ = [
    "configure_default_logging",
    "configure_file_logging",
    "configure_prompt_observability_logging",
    "elapsed_ms_since",
    "get_logger",
    "log_debug",
    "log_info",
    "log_warning",
    "log_warning_exception",
    "log_error",
    "log_exception",
    "log_timing",
]
