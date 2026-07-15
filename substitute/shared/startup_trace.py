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

"""Record bounded startup lifecycle trace events as prompt-safe JSONL."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
import json
from pathlib import Path
from threading import RLock
from typing import IO, ContextManager

from substitute.shared.logging.logger import get_logger, log_warning

Clock = Callable[[], int]
Scheduler = Callable[[int, Callable[[], None]], None]

_LOGGER = get_logger("shared.startup_trace")
_TRACE_FILE_NAME = "startup-trace.jsonl"
_MAX_EVENT_COUNT = 20_000
_MAX_FIELD_COUNT = 32
_MAX_STRING_LENGTH = 160
_MAX_SEQUENCE_LENGTH = 16
_MAX_MAPPING_LENGTH = 16
_FORBIDDEN_FIELD_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "file",
    "password",
    "path",
    "prompt",
    "secret",
    "selected",
    "session",
    "text",
    "token",
    "trigger",
    "url",
)
_FORBIDDEN_EXACT_FIELD_NAMES = frozenset(
    {
        "command",
        "endpoint",
        "error",
        "install_root",
        "line",
        "log_path",
        "trace_path",
    }
)
_SAFE_FIELD_NAMES = frozenset(
    {
        "path_suffix",
        "token_count",
        "error_type",
    }
)


@dataclass
class StartupTraceRecorder:
    """Write startup trace marks and spans without exposing sensitive fields."""

    trace_path: Path | None = None
    clock_ns: Clock | None = None
    _handle: IO[str] | None = field(init=False, default=None, repr=False)
    _enabled: bool = field(init=False, default=False, repr=False)
    _closed: bool = field(init=False, default=False, repr=False)
    _sequence: int = field(init=False, default=0, repr=False)
    _lock: RLock = field(init=False, default_factory=RLock, repr=False)
    _failure_reported: bool = field(init=False, default=False, repr=False)

    def __post_init__(self) -> None:
        """Open the trace file when a path is configured."""

        if self.trace_path is None:
            return
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._handle = self.trace_path.open("a", encoding="utf-8")
        except OSError as error:
            self._disable_after_failure("open", error)
            return
        self._enabled = True

    @property
    def enabled(self) -> bool:
        """Return whether this recorder is currently writing trace events."""

        return self._enabled and not self._closed and self._handle is not None

    def close(self) -> None:
        """Flush and close the configured trace file."""

        with self._lock:
            self._closed = True
            handle = self._handle
            self._handle = None
            self._enabled = False
        if handle is None:
            return
        try:
            handle.flush()
            handle.close()
        except OSError as error:
            self._disable_after_failure("close", error)

    def mark(self, event: str, **fields: object) -> None:
        """Record one startup lifecycle mark."""

        self._write_record("mark", event, fields)

    @contextmanager
    def span(self, event: str, **fields: object) -> Iterator[None]:
        """Record one startup lifecycle span around a block."""

        if not self.enabled:
            yield
            return
        started_ns = self._now_ns()
        try:
            yield
        except BaseException as error:
            ended_ns = self._now_ns()
            failure_fields = dict(fields)
            failure_fields["error_type"] = type(error).__name__
            self._write_record(
                "span",
                event,
                failure_fields,
                elapsed_ns=max(0, ended_ns - started_ns),
                timestamp_ns=ended_ns,
            )
            raise
        else:
            ended_ns = self._now_ns()
            self._write_record(
                "span",
                event,
                fields,
                elapsed_ns=max(0, ended_ns - started_ns),
                timestamp_ns=ended_ns,
            )

    def qtimer_single_shot(
        self,
        name: str,
        scheduler: Scheduler,
        delay_ms: int,
        callback: Callable[[], None],
    ) -> None:
        """Schedule one Qt timer callback while tracing queue and fire timing."""

        if not self.enabled:
            scheduler(delay_ms, callback)
            return
        queued_ns = self._now_ns()
        self.mark(
            "qtimer.single_shot.scheduled",
            timer_name=name,
            delay_ms=delay_ms,
        )

        def traced_callback() -> None:
            try:
                callback()
            except BaseException as error:
                ended_ns = self._now_ns()
                self._write_record(
                    "span",
                    "qtimer.single_shot.failed",
                    {
                        "timer_name": name,
                        "delay_ms": delay_ms,
                        "error_type": type(error).__name__,
                    },
                    elapsed_ns=max(0, ended_ns - queued_ns),
                    timestamp_ns=ended_ns,
                )
                raise
            ended_ns = self._now_ns()
            self._write_record(
                "span",
                "qtimer.single_shot.fired",
                {"timer_name": name, "delay_ms": delay_ms},
                elapsed_ns=max(0, ended_ns - queued_ns),
                timestamp_ns=ended_ns,
            )

        scheduler(delay_ms, traced_callback)

    def _write_record(
        self,
        kind: str,
        event: str,
        fields: Mapping[str, object],
        *,
        elapsed_ns: int | None = None,
        timestamp_ns: int | None = None,
    ) -> None:
        """Serialize and write one trace record when recording is active."""

        with self._lock:
            if not self.enabled or self._sequence >= _MAX_EVENT_COUNT:
                return
            self._sequence += 1
            record: dict[str, object] = {
                "event": _sanitize_event_name(event),
                "fields": _sanitize_fields(fields),
                "kind": kind,
                "sequence": self._sequence,
                "timestamp_ns": timestamp_ns
                if timestamp_ns is not None
                else self._now_ns(),
            }
            if elapsed_ns is not None:
                record["elapsed_ns"] = elapsed_ns
            payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
            handle = self._handle
            if handle is None:
                return
            try:
                handle.write(f"{payload}\n")
                handle.flush()
            except OSError as error:
                self._disable_after_failure("write", error)

    def _now_ns(self) -> int:
        """Return the configured monotonic timestamp."""

        if self.clock_ns is not None:
            return self.clock_ns()
        import time

        return time.perf_counter_ns()

    def _disable_after_failure(self, operation: str, error: OSError) -> None:
        """Disable trace writes after an IO failure without interrupting startup."""

        with self._lock:
            self._enabled = False
            self._closed = True
            self._handle = None
            if self._failure_reported:
                return
            self._failure_reported = True
        log_warning(
            _LOGGER,
            "Startup trace recorder unavailable",
            operation=operation,
            error_type=type(error).__name__,
        )


_TRACE = StartupTraceRecorder()


def configure_startup_trace(logs_dir: Path, *, clock_ns: Clock | None = None) -> Path:
    """Configure process startup trace recording under the supplied log directory."""

    global _TRACE
    trace_path = Path(logs_dir).resolve() / _TRACE_FILE_NAME
    _TRACE.close()
    _TRACE = StartupTraceRecorder(trace_path=trace_path, clock_ns=clock_ns)
    return trace_path


def startup_trace() -> StartupTraceRecorder:
    """Return the process startup trace recorder."""

    return _TRACE


def trace_mark(event: str, **fields: object) -> None:
    """Record one startup trace mark on the process recorder."""

    _TRACE.mark(event, **fields)


def trace_span(event: str, **fields: object) -> ContextManager[None]:
    """Return a startup trace span context manager from the process recorder."""

    return _TRACE.span(event, **fields)


def trace_qtimer_single_shot(
    name: str,
    scheduler: Scheduler,
    delay_ms: int,
    callback: Callable[[], None],
) -> None:
    """Schedule one Qt single-shot callback through the process recorder."""

    _TRACE.qtimer_single_shot(name, scheduler, delay_ms, callback)


def close_startup_trace() -> None:
    """Close the process startup trace recorder."""

    _TRACE.close()


def _sanitize_event_name(event: str) -> str:
    """Return a bounded event name for JSONL output."""

    clean_event = event.strip() or "startup.unnamed"
    return clean_event[:_MAX_STRING_LENGTH]


def _sanitize_fields(fields: Mapping[str, object]) -> dict[str, object]:
    """Return prompt-safe fields plus rejection metadata."""

    sanitized: dict[str, object] = {}
    rejected_count = 0
    for raw_name, value in sorted(fields.items()):
        if len(sanitized) >= _MAX_FIELD_COUNT:
            rejected_count += 1
            continue
        field_name = raw_name.strip()
        if not field_name or not _is_safe_field_name(field_name):
            rejected_count += 1
            continue
        sanitized_value = _sanitize_value(value)
        if sanitized_value is _RejectedValue:
            rejected_count += 1
            continue
        sanitized[field_name] = sanitized_value
    if rejected_count:
        sanitized["rejected_field_count"] = rejected_count
    return sanitized


def _is_safe_field_name(field_name: str) -> bool:
    """Return whether a field name is suitable for startup trace output."""

    normalized = field_name.lower().replace("-", "_")
    if normalized in _SAFE_FIELD_NAMES:
        return True
    if normalized in _FORBIDDEN_EXACT_FIELD_NAMES:
        return False
    return not any(fragment in normalized for fragment in _FORBIDDEN_FIELD_FRAGMENTS)


def _sanitize_value(value: object) -> object:
    """Return a JSON-safe scalar, mapping, or sequence for trace output."""

    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        if _string_looks_sensitive(value):
            return _RejectedValue
        return value[:_MAX_STRING_LENGTH]
    if isinstance(value, Path | BaseException):
        return _RejectedValue
    if isinstance(value, Mapping):
        return _sanitize_mapping_value(value)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return _sanitize_sequence_value(value)
    return _RejectedValue


def _sanitize_mapping_value(value: Mapping[object, object]) -> object:
    """Return a bounded JSON-safe mapping value."""

    sanitized: dict[str, object] = {}
    for key, item in list(value.items())[:_MAX_MAPPING_LENGTH]:
        key_text = str(key)
        if not key_text or not _is_safe_field_name(key_text):
            continue
        sanitized_item = _sanitize_value(item)
        if sanitized_item is not _RejectedValue:
            sanitized[key_text[:_MAX_STRING_LENGTH]] = sanitized_item
    return sanitized


def _sanitize_sequence_value(value: Sequence[object]) -> object:
    """Return a bounded JSON-safe sequence value."""

    sanitized: list[object] = []
    for item in value[:_MAX_SEQUENCE_LENGTH]:
        sanitized_item = _sanitize_value(item)
        if sanitized_item is not _RejectedValue:
            sanitized.append(sanitized_item)
    return sanitized


def _string_looks_sensitive(value: str) -> bool:
    """Return whether a string appears to be a path, URL, or raw command."""

    if "://" in value or "\\" in value or "/" in value:
        return True
    if len(value) > _MAX_STRING_LENGTH:
        return False
    return False


class _RejectedValueType:
    """Sentinel for values excluded from startup trace output."""


_RejectedValue = _RejectedValueType()


__all__ = [
    "StartupTraceRecorder",
    "close_startup_trace",
    "configure_startup_trace",
    "startup_trace",
    "trace_mark",
    "trace_qtimer_single_shot",
    "trace_span",
]
