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

"""Own prompt projection caret blink timing and viewport repaint scheduling."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtCore import QObject, QRectF, Qt, QTimer
from PySide6.QtWidgets import QApplication, QScrollBar, QWidget

from substitute.presentation.widgets.text_caret import (
    text_caret_blink_interval_ms,
    text_caret_repaint_rect,
)

from .model import PromptProjectionSelection


class PromptSurfaceCaretVisualHost(Protocol):
    """Expose cheap viewport-local state needed by caret visual timing."""

    def viewport(self) -> QWidget:
        """Return the viewport that paints the custom caret."""

    def isVisible(self) -> bool:  # noqa: N802
        """Return whether the surface is currently visible."""

    def _caret_focus_owner_has_focus(self) -> bool:
        """Return whether the widget that owns caret focus is active."""

    def _current_caret_rect(self) -> QRectF:
        """Return the current viewport-local caret rectangle."""

    def _current_caret_document_rect(self) -> QRectF:
        """Return the current document-local caret rectangle."""

    def _log_transient_caret_used(self, *, operation: str) -> None:
        """Record that transient caret geometry was consumed."""

    def _reorder_preview_is_active(self) -> bool:
        """Return whether a reorder preview currently suppresses the live caret."""

    def _selection(self) -> PromptProjectionSelection:
        """Return the current source-backed selection."""

    def _valid_transient_caret_document_rect(self) -> QRectF | None:
        """Return valid transient document-local caret geometry, if present."""

    def _visible_scroll_bar(self) -> QScrollBar:
        """Return the scrollbar that owns the visible vertical offset."""


class PromptSurfaceCaretVisualController:
    """Coordinate caret blink phase, repaint invalidation, and visibility scrolling."""

    def __init__(
        self,
        host: PromptSurfaceCaretVisualHost,
        *,
        is_alive: Callable[[QObject], bool],
        parent: QObject,
    ) -> None:
        """Bind caret visuals to a surface host and Qt lifecycle owner."""

        self._host = host
        self._is_alive = is_alive
        self._blink_timer = QTimer(parent)
        self._blink_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._blink_timer.timeout.connect(self.toggle_caret_blink_visibility)
        self._blink_visible = False
        self._blink_enabled = False

    @property
    def blink_timer(self) -> QTimer:
        """Return the Qt timer that owns caret blink ticks."""

        return self._blink_timer

    @property
    def blink_visible(self) -> bool:
        """Return whether the current blink phase paints the caret."""

        return self._blink_visible

    @blink_visible.setter
    def blink_visible(self, visible: bool) -> None:
        """Set the blink phase for lifecycle characterization tests."""

        self._blink_visible = visible

    @property
    def blink_enabled(self) -> bool:
        """Return whether blinking is active for the current system setting."""

        return self._blink_enabled

    @blink_enabled.setter
    def blink_enabled(self, enabled: bool) -> None:
        """Set blink-enabled state for lifecycle characterization tests."""

        self._blink_enabled = enabled

    def cursor_flash_time_ms(self) -> int:
        """Return the current application caret flash period in milliseconds."""

        return int(QApplication.cursorFlashTime())

    def cursor_blink_interval_ms(self, cursor_flash_time_ms: int) -> int:
        """Return the timer interval used to toggle one full cursor flash cycle."""

        return text_caret_blink_interval_ms(cursor_flash_time_ms)

    def is_caret_blink_enabled(self, cursor_flash_time_ms: int) -> bool:
        """Return whether the current application setting allows caret blinking."""

        return cursor_flash_time_ms > 0

    def set_caret_blink_visible(self, visible: bool) -> None:
        """Persist one caret blink phase and repaint only when it changes."""

        if self._blink_visible == visible:
            return
        self._blink_visible = visible
        self.update_caret_paint()

    def restart_caret_blink_cycle(
        self,
        *,
        cursor_flash_time_ms: int,
    ) -> None:
        """Make the caret visible immediately and restart the blink timer."""

        if not self._host_is_alive():
            return
        if not self.caret_can_paint():
            self.stop_caret_blink_cycle()
            return
        self._blink_enabled = self.is_caret_blink_enabled(cursor_flash_time_ms)
        if not self._blink_enabled:
            self._blink_timer.stop()
            self.set_caret_blink_visible(True)
            return
        self.set_caret_blink_visible(True)
        self._blink_timer.start(self.cursor_blink_interval_ms(cursor_flash_time_ms))

    def stop_caret_blink_cycle(self) -> None:
        """Stop blinking and hide the custom caret until it becomes paintable again."""

        if not self._host_is_alive():
            return
        self._blink_timer.stop()
        self._blink_enabled = False
        self.set_caret_blink_visible(False)

    def toggle_caret_blink_visibility(self) -> None:
        """Advance the caret blink phase for one timer tick."""

        if not self._host_is_alive():
            return
        if not self.caret_can_paint():
            self.stop_caret_blink_cycle()
            return
        self.set_caret_blink_visible(not self._blink_visible)

    def schedule_caret_blink_sync(
        self,
        *,
        reset_cycle: bool,
        cursor_flash_time_ms: Callable[[], int],
    ) -> None:
        """Resolve caret blink state after Qt finishes one focus transition."""

        if not self._host_is_alive():
            return
        QTimer.singleShot(
            0,
            lambda: self.sync_caret_blink_state(
                reset_cycle=reset_cycle,
                cursor_flash_time_ms=cursor_flash_time_ms(),
            ),
        )

    def sync_caret_blink_state(
        self,
        *,
        reset_cycle: bool,
        cursor_flash_time_ms: int,
    ) -> None:
        """Apply caret blink visibility after one focus or visibility lifecycle event."""

        if not self._host_is_alive():
            return
        if not self.caret_can_paint():
            self.stop_caret_blink_cycle()
            return
        if reset_cycle:
            self.restart_caret_blink_cycle(cursor_flash_time_ms=cursor_flash_time_ms)
            return
        self._blink_enabled = self.is_caret_blink_enabled(cursor_flash_time_ms)
        if not self._blink_enabled:
            self._blink_timer.stop()
            self.set_caret_blink_visible(True)
            return
        if not self._blink_timer.isActive():
            self._blink_timer.start(self.cursor_blink_interval_ms(cursor_flash_time_ms))
        self.set_caret_blink_visible(True)

    def caret_can_paint(self) -> bool:
        """Return whether the surface currently owns a visible custom caret."""

        if not self._host_is_alive():
            return False
        viewport = self._host.viewport()
        if not self._is_alive(viewport):
            return False
        if (
            not self._host.isVisible()
            or not viewport.isVisible()
            or self._host._reorder_preview_is_active()
            or not self._host._selection().is_empty
        ):
            return False
        return self._host._caret_focus_owner_has_focus()

    def should_paint_caret(self) -> bool:
        """Return whether the custom caret should be painted in the current frame."""

        return self.caret_can_paint() and self._blink_visible

    def update_caret_paint(self, previous_caret_rect: QRectF | None = None) -> None:
        """Repaint the current and previous caret bounds after a visibility change."""

        repaint_rect = text_caret_repaint_rect(self._host._current_caret_rect())
        if previous_caret_rect is not None:
            repaint_rect = repaint_rect.united(
                text_caret_repaint_rect(previous_caret_rect)
            )
        self._host.viewport().update(repaint_rect)

    def ensure_caret_visible(self) -> None:
        """Scroll the viewport vertically until the caret is visible."""

        if self._host._valid_transient_caret_document_rect() is not None:
            self._host._log_transient_caret_used(operation="ensure_visible")
        caret_rect = self._host._current_caret_document_rect()
        viewport_height = self._host.viewport().height()
        scroll_bar = self._host._visible_scroll_bar()
        next_value = scroll_bar.value()
        if caret_rect.top() < next_value:
            next_value = int(caret_rect.top())
        elif caret_rect.bottom() > next_value + viewport_height:
            next_value = int(caret_rect.bottom() - viewport_height)
        clamped_value = max(scroll_bar.minimum(), min(scroll_bar.maximum(), next_value))
        if clamped_value == scroll_bar.value():
            return
        scroll_bar.setValue(clamped_value)

    def _host_is_alive(self) -> bool:
        """Return whether the host Qt wrapper can still be touched."""

        return self._is_alive(cast(QObject, self._host))


__all__ = [
    "PromptSurfaceCaretVisualController",
    "PromptSurfaceCaretVisualHost",
]
