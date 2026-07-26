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

"""Verify allocation-neutral pointer target resolution ownership."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QPoint, QPointF, QRectF

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_target_resolution import (
    PromptReorderPointerTargetResolutionOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_drop_targets import (
    PromptReorderDropTargetVisual,
    PromptReorderRowDropLane,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)


class _Geometry:
    """Publish immutable target geometry."""

    def __init__(self, state: PromptReorderInteractionGeometryState) -> None:
        """Initialize one inspectable geometry publication."""

        self._state = state

    @property
    def state(self) -> PromptReorderInteractionGeometryState:
        """Return the current immutable geometry state."""

        return self._state


class _RecordingTelemetry(PromptReorderTelemetry):
    """Record pointer-resolution events without using the process logger."""

    def __init__(self) -> None:
        """Initialize an in-memory event sink with every move sampled."""

        super().__init__(pointer_sample_interval=1)
        self.events: list[tuple[str, dict[str, object]]] = []

    def log_event(self, event: str, **context: object) -> None:
        """Record one validated event."""

        self.events.append((event, context))


def test_pointer_target_owner_publishes_changed_and_no_change_paths() -> None:
    """Resolve a changed target once and reuse it on the next pointer sample."""

    target = PromptLineDropTarget(row_index=0, insertion_index=1)
    target_visual = PromptReorderDropTargetVisual(
        target=target,
        hit_rect=QRectF(0.0, 0.0, 100.0, 30.0),
    )
    geometry = _Geometry(
        PromptReorderInteractionGeometryState(
            drop_target_visuals=(target_visual,),
            drop_target_lanes=(
                PromptReorderRowDropLane(
                    row_index=0,
                    visual_row_index=0,
                    hit_rect=QRectF(0.0, 0.0, 100.0, 30.0),
                    slot_visuals=(target_visual,),
                ),
            ),
        )
    )
    gesture = PromptReorderGestureController()
    gesture.begin_pointer_drag(segment_index=3, global_position=QPoint(10, 10))
    gesture.capture_drag_intent_context(
        chip_rect=QRectF(0.0, 0.0, 20.0, 10.0),
        local_pointer=QPointF(10.0, 5.0),
    )
    metrics = PromptReorderInteractionMetricsOwner()
    metrics.begin_gesture(gesture_id=7)
    metrics.begin_pointer_move()
    metrics.leave_pointer_loop()
    telemetry = _RecordingTelemetry()
    diagnostics = PromptReorderInteractionDiagnosticsOwner(
        telemetry=telemetry,
        metrics=metrics,
    )
    owner = PromptReorderPointerTargetResolutionOwner(
        geometry=cast(PromptReorderInteractionGeometry, geometry),
        gesture=gesture,
        metrics=metrics,
        telemetry=telemetry,
        diagnostics=diagnostics,
    )

    changed = owner.resolve(QPointF(20.0, 10.0))
    gesture.set_active_drop_target(target)
    unchanged = owner.resolve(QPointF(20.0, 10.0))

    assert changed is not None and changed.changed
    assert unchanged is not None and not unchanged.changed
    assert gesture.state.active_drop_target == target
    assert geometry.state.active_placement is None
    assert owner.last_resolve_elapsed_ms >= 0.0
    event_names = [event for event, _ in telemetry.events]
    assert "drop_target.changed_rebuild_path" in event_names
    assert "drop_target.no_change_fast_path" in event_names


def test_pointer_target_owner_is_a_noop_without_an_active_drag() -> None:
    """Avoid target work when no semantic drag owns the pointer."""

    geometry = _Geometry(PromptReorderInteractionGeometryState())
    gesture = PromptReorderGestureController()
    metrics = PromptReorderInteractionMetricsOwner()
    telemetry = _RecordingTelemetry()
    owner = PromptReorderPointerTargetResolutionOwner(
        geometry=cast(PromptReorderInteractionGeometry, geometry),
        gesture=gesture,
        metrics=metrics,
        telemetry=telemetry,
        diagnostics=PromptReorderInteractionDiagnosticsOwner(
            telemetry=telemetry,
            metrics=metrics,
        ),
    )

    assert owner.resolve(QPointF(20.0, 10.0)) is None
    assert telemetry.events == []
