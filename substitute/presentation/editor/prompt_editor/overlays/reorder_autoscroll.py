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

from PySide6.QtCore import QPoint, QPointF, QObject, QTimer
from PySide6.QtWidgets import QScrollBar

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.observability import log_reorder_drag_timing, reorder_drag_started_at
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)

_AUTOSCROLL_MARGIN = 36
_AUTOSCROLL_STEP = 24
_AUTOSCROLL_INTERVAL_MS = 30


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


class PromptReorderAutoscrollOwner:
    """Own bounded autoscroll and its complete invalidation lifecycle."""

    def __init__(
        self,
        *,
        parent: QObject,
        scrollbar_provider: Callable[[], QScrollBar],
        overlay_height_provider: Callable[[], int],
        map_global_to_overlay: Callable[[QPoint], QPoint],
        refresh_geometry: Callable[[str], None],
        settle_animation: Callable[[str], None],
        invalidate_refresh: Callable[[], None],
        gesture: PromptReorderGestureController,
        update_target: Callable[[QPointF, bool], bool],
        emit_preview_layout_changed: Callable[[], None],
        metrics: PromptReorderInteractionMetricsOwner,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
        margin: int = _AUTOSCROLL_MARGIN,
        step: int = _AUTOSCROLL_STEP,
        interval_ms: int = _AUTOSCROLL_INTERVAL_MS,
    ) -> None:
        """Initialize autoscroll policy and timer ownership."""

        self._scrollbar_provider = scrollbar_provider
        self._overlay_height_provider = overlay_height_provider
        self._map_global_to_overlay = map_global_to_overlay
        self._refresh_geometry = refresh_geometry
        self._settle_animation = settle_animation
        self._invalidate_refresh = invalidate_refresh
        self._gesture = gesture
        self._update_target = update_target
        self._emit_preview_layout_changed = emit_preview_layout_changed
        self._metrics = metrics
        self._diagnostics = diagnostics
        self._margin = margin
        self._step = step
        self._direction = 0
        self._last_global_position: QPoint | None = None
        self._pointer_update_count = 0
        self._scroll_invalidation_count = 0
        self._noop_step_count = 0
        self._schedule_count = 0
        self._coalesced_count = 0
        self._flush_count = 0
        self._target_refresh_count = 0
        self._pending_invalidation: PromptReorderAutoscrollInvalidation | None = None
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
        self._schedule_count = 0
        self._coalesced_count = 0
        self._flush_count = 0
        self._target_refresh_count = 0

    def counters(self) -> dict[str, int]:
        """Return test-facing autoscroll counters."""

        return {
            "autoscroll_pointer_update_count": self._pointer_update_count,
            "autoscroll_invalidation_count": self._scroll_invalidation_count,
            "autoscroll_noop_step_count": self._noop_step_count,
            "autoscroll_schedule_count": self._schedule_count,
            "autoscroll_coalesced_count": self._coalesced_count,
            "autoscroll_flush_count": self._flush_count,
            "autoscroll_target_refresh_count": self._target_refresh_count,
            "autoscroll_pending_invalidation_count": int(
                self._pending_invalidation is not None
            ),
        }

    def clear_pending_invalidation(self) -> None:
        """Discard queued geometry refresh state at a lifecycle boundary."""

        self._pending_invalidation = None

    def flush_pending_invalidation(self, *, reason: str) -> bool:
        """Consume and apply the latest coalesced scroll invalidation."""

        invalidation = self._pending_invalidation
        if invalidation is None:
            return False
        self._pending_invalidation = None
        self._flush_count += 1
        self._settle_animation(f"autoscroll_flush:{reason}")
        self._refresh_geometry(reason)
        before_target = self._gesture.state.active_drop_target
        self._update_target(
            QPointF(self._map_global_to_overlay(invalidation.global_position)),
            False,
        )
        target_changed = before_target != self._gesture.state.active_drop_target
        if target_changed:
            self._target_refresh_count += 1
        self._diagnostics.log_event(
            "autoscroll.invalidation_flushed",
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            reason=reason,
            direction=invalidation.direction,
            previous_scroll_position=invalidation.previous_scroll_position,
            next_scroll_position=invalidation.next_scroll_position,
            invalidation_index=invalidation.invalidation_index,
            target_changed=target_changed,
        )
        return True

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
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                direction=self._direction,
                scrollbar_position=previous_position,
                scrollbar_minimum=scrollbar.minimum(),
                scrollbar_maximum=scrollbar.maximum(),
            )
            return

        scrollbar.setValue(next_position)
        self._scroll_invalidation_count += 1
        invalidation = PromptReorderAutoscrollInvalidation(
            global_position=QPoint(self._last_global_position),
            direction=self._direction,
            previous_scroll_position=previous_position,
            next_scroll_position=next_position,
            invalidation_index=self._scroll_invalidation_count,
        )
        if self._pending_invalidation is not None:
            self._coalesced_count += 1
        self._pending_invalidation = invalidation
        self._schedule_count += 1
        self._settle_animation("autoscroll_step")
        self._invalidate_refresh()
        self._emit_preview_layout_changed()
        log_reorder_drag_timing(
            "autoscroll.step",
            started_at=started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            direction=self._direction,
            previous_position=previous_position,
            next_position=next_position,
        )


__all__ = [
    "PromptReorderAutoscrollOwner",
    "PromptReorderAutoscrollInvalidation",
]
