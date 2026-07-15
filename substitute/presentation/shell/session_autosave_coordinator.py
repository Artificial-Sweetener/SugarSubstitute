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

"""Coordinate debounced session autosave requests for shell interactions."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Protocol, cast

from PySide6.QtCore import QObject, QTimer


class SessionAutosaveRequestCategory(StrEnum):
    """Name user interactions that request session persistence."""

    TAB_SELECTION = "tab_selection"
    TAB_STRUCTURE = "tab_structure"
    WORKFLOW_MUTATION = "workflow_mutation"
    CANVAS_SELECTION = "canvas_selection"
    LAYOUT_RESIZE = "layout_resize"
    RESTORE_COMPLETION = "restore_completion"


class AutosaveTimerProtocol(Protocol):
    """Describe the QTimer subset used for autosave debouncing."""

    def setSingleShot(self, single_shot: bool) -> None:
        """Configure single-shot behavior."""

    def start(self, delay_ms: int) -> None:
        """Start or restart the timer."""


AutosaveTimerFactory = Callable[[QObject | None], AutosaveTimerProtocol]


def create_qtimer(parent: QObject | None) -> AutosaveTimerProtocol:
    """Create the default Qt timer used by the autosave coordinator."""

    return QTimer(parent)


class SessionAutosaveCoordinator(QObject):
    """Own debounce timers for session autosave intent."""

    def __init__(
        self,
        *,
        request_save: Callable[[SessionAutosaveRequestCategory], None],
        parent: QObject | None = None,
        timer_factory: AutosaveTimerFactory = create_qtimer,
        tab_selection_debounce_ms: int,
        resize_debounce_ms: int,
    ) -> None:
        """Create timers that coalesce high-frequency session save requests."""

        super().__init__(parent)
        self._request_save = request_save
        self._tab_selection_debounce_ms = max(0, int(tab_selection_debounce_ms))
        self._resize_debounce_ms = max(0, int(resize_debounce_ms))
        self._debounce_ms_by_category = {
            SessionAutosaveRequestCategory.TAB_SELECTION: (
                self._tab_selection_debounce_ms
            ),
            SessionAutosaveRequestCategory.TAB_STRUCTURE: (
                self._tab_selection_debounce_ms
            ),
            SessionAutosaveRequestCategory.WORKFLOW_MUTATION: (
                self._tab_selection_debounce_ms
            ),
            SessionAutosaveRequestCategory.CANVAS_SELECTION: (
                self._tab_selection_debounce_ms
            ),
            SessionAutosaveRequestCategory.LAYOUT_RESIZE: self._resize_debounce_ms,
            SessionAutosaveRequestCategory.RESTORE_COMPLETION: (
                self._tab_selection_debounce_ms
            ),
        }
        self._timers = {
            category: self._create_timer(
                timer_factory,
                self._flush_callback(category),
            )
            for category in SessionAutosaveRequestCategory
        }

    @property
    def tab_selection_timer(self) -> AutosaveTimerProtocol:
        """Return the tab-selection debounce timer for Qt ownership visibility."""

        return self._timers[SessionAutosaveRequestCategory.TAB_SELECTION]

    @property
    def resize_timer(self) -> AutosaveTimerProtocol:
        """Return the resize debounce timer for Qt ownership visibility."""

        return self._timers[SessionAutosaveRequestCategory.LAYOUT_RESIZE]

    def request(self, category: SessionAutosaveRequestCategory) -> None:
        """Request a session save with category-specific debounce policy."""

        self._timers[category].start(self._debounce_ms_by_category[category])

    def flush(self, category: SessionAutosaveRequestCategory) -> None:
        """Persist the latest autosave request for one category immediately."""

        self._flush(category)

    def flush_tab_selection(self) -> None:
        """Persist the latest tab-selection autosave request immediately."""

        self._flush(SessionAutosaveRequestCategory.TAB_SELECTION)

    def flush_resize(self) -> None:
        """Persist the latest resize autosave request immediately."""

        self._flush(SessionAutosaveRequestCategory.LAYOUT_RESIZE)

    def _create_timer(
        self,
        timer_factory: AutosaveTimerFactory,
        callback: Callable[[], None],
    ) -> AutosaveTimerProtocol:
        """Create a single-shot Qt timer connected to one callback."""

        timer = timer_factory(self)
        timer.setSingleShot(True)
        timeout_signal = getattr(timer, "timeout")
        connect = cast(
            Callable[[Callable[[], None]], None],
            getattr(timeout_signal, "connect"),
        )
        connect(callback)
        return timer

    def _flush_callback(
        self,
        category: SessionAutosaveRequestCategory,
    ) -> Callable[[], None]:
        """Return a typed timer callback for one autosave category."""

        def callback() -> None:
            """Flush the category captured when the timer was created."""

            self._flush(category)

        return callback

    def _flush(self, category: SessionAutosaveRequestCategory) -> None:
        """Forward a settled autosave request to persistence policy."""

        self._request_save(category)


__all__ = [
    "AutosaveTimerFactory",
    "AutosaveTimerProtocol",
    "create_qtimer",
    "SessionAutosaveCoordinator",
    "SessionAutosaveRequestCategory",
]
