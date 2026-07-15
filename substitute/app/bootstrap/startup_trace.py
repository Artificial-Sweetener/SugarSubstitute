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

"""Own bootstrap startup visibility tracing and expose real trace helpers."""

from __future__ import annotations

from typing import Any, ClassVar, cast

from substitute.shared.startup_trace import (
    StartupTraceRecorder,
    close_startup_trace,
    configure_startup_trace,
    startup_trace,
    trace_mark,
    trace_span,
)

_QEVENT_TYPE: Any = None
try:
    from PySide6.QtCore import QEvent as _QtQEvent
    from PySide6.QtCore import QObject
except (ImportError, AttributeError):  # pragma: no cover - lightweight test stubs

    class QObject:  # type: ignore[no-redef]
        """Fallback QObject used when Qt is unavailable in lightweight tests."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            """Accept QObject-like construction arguments."""

        def eventFilter(self, _watched: object, _event: object) -> bool:
            """Return the default event-filter result."""

            return False

else:
    _QEVENT_TYPE = _QtQEvent

_VISIBILITY_EVENT_NAMES = {
    "Polish",
    "Show",
    "Resize",
    "LayoutRequest",
    "UpdateRequest",
    "Paint",
    "WindowActivate",
}


class StartupVisibilityEventFilter(QObject):
    """Trace first visible-shell Qt events during startup diagnostics."""

    _EVENT_TYPES: ClassVar[dict[int, str]] = {}

    def __init__(self, label: str) -> None:
        """Initialize a visibility event filter for one watched object label."""

        super().__init__()
        self._label = label
        self._seen: set[str] = set()
        self._counts: dict[str, int] = {}
        self._ensure_event_types()

    def eventFilter(self, watched: object, event: object) -> bool:
        """Record first and repeated visibility event counts for watched objects."""

        event_type_value = _event_type_value(event)
        event_name = self._EVENT_TYPES.get(event_type_value)
        if event_name in _VISIBILITY_EVENT_NAMES:
            self._counts[event_name] = self._counts.get(event_name, 0) + 1
            if event_name not in self._seen:
                self._seen.add(event_name)
                trace_mark(
                    "startup.visibility.first_event",
                    label=self._label,
                    event_type=event_name,
                    watched_type=type(watched).__name__,
                    count=self._counts[event_name],
                    width=_safe_call_int(watched, "width"),
                    height=_safe_call_int(watched, "height"),
                )
        parent_filter = cast(Any, super()).eventFilter
        return bool(parent_filter(watched, event))

    def flush_summary(self) -> None:
        """Emit summary counts collected by this visibility filter."""

        if not self._counts:
            return
        trace_mark(
            "startup.visibility.summary",
            label=self._label,
            counts=dict(sorted(self._counts.items())),
        )

    @classmethod
    def _ensure_event_types(cls) -> None:
        """Populate event-type names once from Qt event metadata."""

        if cls._EVENT_TYPES:
            return
        if _QEVENT_TYPE is None:
            return
        type_container = getattr(_QEVENT_TYPE, "Type", None)
        for event_name in _VISIBILITY_EVENT_NAMES:
            value = getattr(type_container, event_name, None)
            if value is None:
                value = getattr(_QEVENT_TYPE, event_name, None)
            event_value = _event_enum_int(value)
            if event_value is not None:
                cls._EVENT_TYPES[event_value] = event_name


def _event_type_value(event: object) -> int:
    """Return an integer Qt event type value when available."""

    event_type = getattr(event, "type", None)
    raw_value = event_type() if callable(event_type) else event_type
    return _event_enum_int(raw_value) or -1


def _event_enum_int(value: object) -> int | None:
    """Return an integer from a Qt enum-like value."""

    if value is None:
        return None
    enum_value = getattr(value, "value", value)
    try:
        return int(cast(Any, enum_value))
    except (TypeError, ValueError):
        return None


def _safe_call_int(watched: object, method_name: str) -> int | None:
    """Call one zero-argument widget method and coerce the result to int."""

    method = getattr(watched, method_name, None)
    if not callable(method):
        return None
    try:
        return int(cast(Any, method()))
    except (RuntimeError, TypeError, ValueError):
        return None


__all__ = [
    "StartupTraceRecorder",
    "StartupVisibilityEventFilter",
    "close_startup_trace",
    "configure_startup_trace",
    "startup_trace",
    "trace_mark",
    "trace_span",
]
