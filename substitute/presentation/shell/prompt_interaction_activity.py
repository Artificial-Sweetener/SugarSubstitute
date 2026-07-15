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

"""Track prompt editor interactions for temporary UI prioritization decisions."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from PySide6.QtCore import QEvent, QObject, Qt

_DEFAULT_ACTIVE_WINDOW_MS = 250
_PROMPT_INTERACTION_ANCESTOR_NAMES = frozenset(
    {
        "PromptEditor",
        "SegmentReorderOverlay",
        "_SegmentChip",
        "PromptReorderDragProxyWidget",
    }
)
_PROMPT_INTERACTION_EVENT_TYPES = frozenset(
    {
        QEvent.Type.KeyPress,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.Wheel,
        QEvent.Type.DragEnter,
        QEvent.Type.DragMove,
        QEvent.Type.Drop,
    }
)


class PromptInteractionActivityTracker(QObject):
    """Record recent prompt interaction without coupling schedulers to editor widgets."""

    def __init__(
        self,
        *,
        active_window_ms: int = _DEFAULT_ACTIVE_WINDOW_MS,
        clock: Callable[[], float] = perf_counter,
        parent: QObject | None = None,
    ) -> None:
        """Create an activity tracker with an injectable monotonic clock."""

        super().__init__(parent)
        self._active_window_ms = max(1, int(active_window_ms))
        self._clock = clock
        self._last_prompt_interaction_at: float | None = None
        self._installed_application: QObject | None = None

    def install_on_application(self, application: QObject) -> None:
        """Observe application events and record prompt editor interaction."""

        if self._installed_application is application:
            return
        if self._installed_application is not None:
            self._installed_application.removeEventFilter(self)
        application.installEventFilter(self)
        self._installed_application = application

    def record_prompt_interaction(self) -> None:
        """Mark the current monotonic time as prompt interaction activity."""

        self._last_prompt_interaction_at = self._clock()

    def is_prompt_interaction_active(self) -> bool:
        """Return whether prompt interaction happened inside the active window."""

        elapsed_ms = self.ms_since_last_prompt_interaction()
        return elapsed_ms is not None and elapsed_ms <= self._active_window_ms

    def ms_since_last_prompt_interaction(self) -> float | None:
        """Return elapsed milliseconds since the last prompt interaction event."""

        if self._last_prompt_interaction_at is None:
            return None
        return max(0.0, (self._clock() - self._last_prompt_interaction_at) * 1000.0)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Record active prompt interactions routed through prompt editor widgets."""

        if _is_prompt_interaction_event(event) and _has_prompt_interaction_ancestor(
            watched
        ):
            self.record_prompt_interaction()
        return super().eventFilter(watched, event)


def _is_prompt_interaction_event(event: QEvent) -> bool:
    """Return whether one Qt event should prioritize prompt interaction work."""

    event_type = event.type()
    if event_type in _PROMPT_INTERACTION_EVENT_TYPES:
        return True
    if event_type is QEvent.Type.MouseMove:
        buttons = getattr(event, "buttons", None)
        if not callable(buttons):
            return False
        return bool(buttons() & Qt.MouseButton.AllButtons)
    return False


def _has_prompt_interaction_ancestor(target: QObject) -> bool:
    """Return whether a QObject belongs to a prompt interaction widget subtree."""

    current: QObject | None = target
    while current is not None:
        if type(current).__name__ in _PROMPT_INTERACTION_ANCESTOR_NAMES:
            return True
        current = current.parent()
    return False


__all__ = ["PromptInteractionActivityTracker"]
