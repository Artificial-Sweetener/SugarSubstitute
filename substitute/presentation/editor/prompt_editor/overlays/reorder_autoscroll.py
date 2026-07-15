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

"""Own prompt reorder autoscroll timer and scrollbar mutation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QObject, QTimer
from PySide6.QtWidgets import QScrollBar

from ..projection.observability import log_reorder_drag_timing, reorder_drag_started_at


_AUTOSCROLL_MARGIN = 36
_AUTOSCROLL_STEP = 24
_AUTOSCROLL_INTERVAL_MS = 30


@dataclass(frozen=True, slots=True)
class PromptReorderAutoscrollContext:
    """Describe diagnostic identity for one autoscroll tick."""

    gesture_id: int | None
    event_id: int | None


@dataclass(frozen=True, slots=True)
class PromptReorderAutoscrollInvalidation:
    """Describe one scrollbar movement that invalidates reorder geometry.

    The autoscroll controller owns the visual timer and scrollbar mutation. It
    emits this display invalidation so interaction owners can coalesce geometry
    and preview refreshes without rebuilding projection synchronously per tick.
    """

    global_position: QPoint
    direction: int
    previous_scroll_position: int
    next_scroll_position: int
    invalidation_index: int


class PromptReorderAutoscrollController:
    """Run bounded reorder autoscroll as a presentation UI-frame timer."""

    def __init__(
        self,
        *,
        parent: QObject,
        scrollbar_provider: Callable[[], QScrollBar],
        overlay_height_provider: Callable[[], int],
        map_global_to_overlay: Callable[[QPoint], QPoint],
        step_callback: Callable[[PromptReorderAutoscrollInvalidation], None],
        context_provider: Callable[[], PromptReorderAutoscrollContext],
        margin: int = _AUTOSCROLL_MARGIN,
        step: int = _AUTOSCROLL_STEP,
        interval_ms: int = _AUTOSCROLL_INTERVAL_MS,
    ) -> None:
        """Initialize autoscroll policy and timer ownership."""

        self._scrollbar_provider = scrollbar_provider
        self._overlay_height_provider = overlay_height_provider
        self._map_global_to_overlay = map_global_to_overlay
        self._step_callback = step_callback
        self._context_provider = context_provider
        self._margin = margin
        self._step = step
        self._direction = 0
        self._last_global_position: QPoint | None = None
        self._pointer_update_count = 0
        self._scroll_invalidation_count = 0
        self._noop_step_count = 0
        self._timer = QTimer(parent)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._apply_step)

    @property
    def direction(self) -> int:
        """Return the current autoscroll direction."""

        return self._direction

    @property
    def last_global_position(self) -> QPoint | None:
        """Return the last pointer position used for autoscroll."""

        return self._last_global_position

    def is_active(self) -> bool:
        """Return whether the autoscroll timer is currently active."""

        return self._timer.isActive()

    def reset_counters(self) -> None:
        """Reset per-gesture autoscroll input and invalidation counters."""

        self._pointer_update_count = 0
        self._scroll_invalidation_count = 0
        self._noop_step_count = 0

    def counters(self) -> dict[str, int]:
        """Return test-facing autoscroll counters."""

        return {
            "autoscroll_pointer_update_count": self._pointer_update_count,
            "autoscroll_invalidation_count": self._scroll_invalidation_count,
            "autoscroll_noop_step_count": self._noop_step_count,
        }

    def update_for_pointer(self, global_position: QPoint) -> None:
        """Start or stop autoscroll based on the pointer position."""

        self._pointer_update_count += 1
        self._last_global_position = global_position
        scrollbar = self._scrollbar_provider()
        if scrollbar.maximum() == 0:
            self.stop()
            return

        local_pos = self._map_global_to_overlay(global_position)
        direction = 0
        if local_pos.y() <= self._margin:
            direction = -1
        elif local_pos.y() >= self._overlay_height_provider() - self._margin:
            direction = +1

        if direction == 0:
            self.stop()
            return
        self._direction = direction
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        """Stop any active autoscroll timer."""

        self._direction = 0
        self._timer.stop()

    def apply_step_for_tests(self) -> None:
        """Advance one autoscroll tick deterministically in tests."""

        self._apply_step()

    def _apply_step(self) -> None:
        """Advance the editor scrollbar one step while dragging near an edge."""

        if self._direction == 0 or self._last_global_position is None:
            return

        context = self._context_provider()
        started_at = reorder_drag_started_at()
        scrollbar = self._scrollbar_provider()
        previous_position = scrollbar.value()
        next_position = max(
            scrollbar.minimum(),
            min(
                scrollbar.maximum(),
                previous_position + (self._direction * self._step),
            ),
        )
        if next_position == previous_position:
            self._noop_step_count += 1
            log_reorder_drag_timing(
                "autoscroll.noop",
                started_at=started_at,
                gesture_id=context.gesture_id,
                event_id=context.event_id,
                direction=self._direction,
                scrollbar_position=previous_position,
                scrollbar_minimum=scrollbar.minimum(),
                scrollbar_maximum=scrollbar.maximum(),
            )
            return

        scrollbar.setValue(next_position)
        self._scroll_invalidation_count += 1
        self._step_callback(
            PromptReorderAutoscrollInvalidation(
                global_position=QPoint(self._last_global_position),
                direction=self._direction,
                previous_scroll_position=previous_position,
                next_scroll_position=next_position,
                invalidation_index=self._scroll_invalidation_count,
            )
        )
        log_reorder_drag_timing(
            "autoscroll.step",
            started_at=started_at,
            gesture_id=context.gesture_id,
            event_id=context.event_id,
            direction=self._direction,
            previous_position=previous_position,
            next_position=next_position,
        )


__all__ = [
    "PromptReorderAutoscrollContext",
    "PromptReorderAutoscrollController",
    "PromptReorderAutoscrollInvalidation",
]
