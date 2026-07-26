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

"""Own the allocation-bounded pointer-move reorder transition."""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QPoint, QPointF

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.observability import (
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from .reorder_autoscroll import PromptReorderAutoscrollOwner
from .reorder_drag_proxy_visual_owner import PromptReorderDragProxyVisualOwner
from .reorder_gesture_controller import (
    PromptReorderDragIntent,
    PromptReorderGestureController,
)
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_interaction_intents import PromptReorderInteractionIntentOwner
from .reorder_pointer_target_transition import (
    PromptReorderPointerTargetTransitionOwner,
)
from .reorder_telemetry import PromptReorderTelemetry

_SLOW_DRAG_MOVE_MS = 16.0


class PromptReorderPointerMoveOwner:
    """Apply one complete pointer-move transition over focused collaborators."""

    def __init__(
        self,
        *,
        gesture: PromptReorderGestureController,
        intents: PromptReorderInteractionIntentOwner,
        metrics: PromptReorderInteractionMetricsOwner,
        telemetry: PromptReorderTelemetry,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
        drag_proxy: PromptReorderDragProxyVisualOwner,
        target_transition: PromptReorderPointerTargetTransitionOwner,
        autoscroll: PromptReorderAutoscrollOwner,
        geometry: PromptReorderInteractionGeometry,
        map_global_to_overlay: Callable[[QPoint], QPoint],
    ) -> None:
        """Store stable owners and one bound coordinate adapter."""

        self._gesture = gesture
        self._intents = intents
        self._metrics = metrics
        self._telemetry = telemetry
        self._diagnostics = diagnostics
        self._drag_proxy = drag_proxy
        self._target_transition = target_transition
        self._autoscroll = autoscroll
        self._geometry = geometry
        self._map_global_to_overlay = map_global_to_overlay

    def move(self, segment_index: int, global_position: QPoint) -> None:
        """Update proxy, target, and autoscroll for the active dragged segment."""

        if self._gesture.state.dragged_segment_index != segment_index:
            return
        self._intents.publish_drag(
            PromptReorderDragIntent(
                phase="move",
                segment_index=segment_index,
                global_position=global_position,
            )
        )
        total_started_at = reorder_drag_started_at()
        event_id = self._metrics.begin_event()
        work_unit_id = self._metrics.next_work_unit()
        move_count = self._metrics.begin_pointer_move()
        previous_target = self._gesture.state.active_drop_target
        self._gesture.update_pointer_drag_position(global_position)
        pre_target_sample = self._telemetry.should_log_pointer_event(
            move_count=move_count,
            target_changed=False,
        )
        if pre_target_sample:
            self._diagnostics.log_event(
                "pointer_loop.begin",
                gesture_id=self._metrics.gesture_id,
                event_id=event_id,
                work_unit_id=work_unit_id,
                move_count=move_count,
                dragged_segment_index=segment_index,
            )
        try:
            phase_started_at = reorder_drag_started_at()
            proxy_elapsed_ms = self._drag_proxy.move(
                global_position,
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                log_timing=pre_target_sample,
            )
            if pre_target_sample:
                self._diagnostics.log_timing(
                    "drag_move.proxy",
                    started_at=phase_started_at,
                    gesture_id=self._metrics.gesture_id,
                    event_id=event_id,
                    work_unit_id=work_unit_id,
                    move_count=move_count,
                )
            phase_started_at = reorder_drag_started_at()
            self._target_transition.update(
                QPointF(self._map_global_to_overlay(global_position))
            )
            target_changed = previous_target != self._gesture.state.active_drop_target
            pointer_sample = self._telemetry.should_log_pointer_event(
                move_count=move_count,
                target_changed=target_changed,
            )
            if pointer_sample:
                target_elapsed_ms = self._diagnostics.log_timing(
                    "drag_move.target_update",
                    started_at=phase_started_at,
                    gesture_id=self._metrics.gesture_id,
                    event_id=event_id,
                    work_unit_id=work_unit_id,
                    move_count=move_count,
                    previous_target_kind=reorder_drag_target_kind(previous_target),
                    active_target_kind=reorder_drag_target_kind(
                        self._gesture.state.active_drop_target
                    ),
                    target_changed=target_changed,
                )
            else:
                target_elapsed_ms = (time.perf_counter() - phase_started_at) * 1000.0
            phase_started_at = reorder_drag_started_at()
            self._autoscroll.update_for_pointer(global_position)
            if pointer_sample:
                autoscroll_elapsed_ms = self._diagnostics.log_timing(
                    "drag_move.autoscroll",
                    started_at=phase_started_at,
                    gesture_id=self._metrics.gesture_id,
                    event_id=event_id,
                    work_unit_id=work_unit_id,
                    move_count=move_count,
                    autoscroll_direction=self._autoscroll.direction,
                )
            else:
                autoscroll_elapsed_ms = (
                    time.perf_counter() - phase_started_at
                ) * 1000.0
        finally:
            self._metrics.leave_pointer_loop()
        if pointer_sample:
            drag_elapsed_ms = self._diagnostics.log_timing(
                "drag_move.total",
                started_at=total_started_at,
                gesture_id=self._metrics.gesture_id,
                event_id=event_id,
                work_unit_id=work_unit_id,
                move_count=move_count,
                dragged_segment_index=segment_index,
                active_target_kind=reorder_drag_target_kind(
                    self._gesture.state.active_drop_target
                ),
                target_changed=target_changed,
                lane_count=len(self._geometry.state.drop_target_lanes),
                visual_target_count=len(self._geometry.state.drop_target_visuals),
                proxy_elapsed_ms=f"{proxy_elapsed_ms:.3f}",
                target_elapsed_ms=f"{target_elapsed_ms:.3f}",
                autoscroll_elapsed_ms=f"{autoscroll_elapsed_ms:.3f}",
            )
            self._diagnostics.log_event(
                "pointer_loop.allowed_work",
                gesture_id=self._metrics.gesture_id,
                event_id=event_id,
                work_unit_id=work_unit_id,
                proxy_elapsed_ms=f"{proxy_elapsed_ms:.3f}",
                target_elapsed_ms=f"{target_elapsed_ms:.3f}",
                autoscroll_elapsed_ms=f"{autoscroll_elapsed_ms:.3f}",
            )
            self._diagnostics.log_event(
                "pointer_loop.end",
                gesture_id=self._metrics.gesture_id,
                event_id=event_id,
                work_unit_id=work_unit_id,
                elapsed_ms=f"{drag_elapsed_ms:.3f}",
            )
        else:
            drag_elapsed_ms = (time.perf_counter() - total_started_at) * 1000.0
        self._metrics.record_pointer_move_outcome(
            elapsed_ms=drag_elapsed_ms,
            target_changed=target_changed,
        )
        self._diagnostics.log_slow_path_if_needed(
            "slow.drag_move",
            elapsed_ms=drag_elapsed_ms,
            threshold_ms=_SLOW_DRAG_MOVE_MS,
            move_count=move_count,
            target_changed=target_changed,
            active_target_kind=reorder_drag_target_kind(
                self._gesture.state.active_drop_target
            ),
        )


__all__ = ["PromptReorderPointerMoveOwner"]
