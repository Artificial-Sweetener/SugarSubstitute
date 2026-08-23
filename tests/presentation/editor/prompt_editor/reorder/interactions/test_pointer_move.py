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

"""Verify allocation-bounded prompt-reorder pointer-move transitions."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QPoint, QPointF

from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_autoscroll import (
    PromptReorderAutoscrollOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_drag_proxy_visual_owner import (
    PromptReorderDragProxyVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_intents import (
    PromptReorderInteractionIntentOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_move_owner import (
    PromptReorderPointerMoveOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_target_transition import (
    PromptReorderPointerTargetTransitionOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)


class _Intents:
    """Capture published pointer intents."""

    def __init__(self) -> None:
        """Initialize an empty publication list."""

        self.published: list[object] = []

    def publish_drag(self, intent: object) -> None:
        """Retain one intent."""

        self.published.append(intent)


class _Telemetry:
    """Disable sampled diagnostics for the ordinary pointer path."""

    def should_log_pointer_event(
        self,
        *,
        move_count: int,
        target_changed: bool,
    ) -> bool:
        """Return false without allocating diagnostic context."""

        del move_count, target_changed
        return False


class _Diagnostics:
    """Capture only the always-evaluated slow-path decision."""

    def __init__(self) -> None:
        """Initialize empty observations."""

        self.events: list[str] = []
        self.slow_checks = 0

    def log_event(self, event: str, **_context: object) -> None:
        """Retain one event."""

        self.events.append(event)

    def log_timing(self, event: str, **_context: object) -> float:
        """Retain one timing event."""

        self.events.append(event)
        return 0.1

    def log_slow_path_if_needed(self, _event: str, **_context: object) -> None:
        """Record the constant-time threshold check."""

        self.slow_checks += 1


class _DragProxy:
    """Capture one proxy movement."""

    def __init__(self) -> None:
        """Initialize movement counting."""

        self.move_count = 0

    def move(self, _position: QPoint, **_context: object) -> float:
        """Record one proxy move."""

        self.move_count += 1
        return 0.1


class _TargetTransition:
    """Capture one local target update."""

    def __init__(self) -> None:
        """Initialize update capture."""

        self.positions: list[QPointF] = []

    def update(self, position: QPointF) -> bool:
        """Retain one local pointer position."""

        self.positions.append(position)
        return False


class _Autoscroll:
    """Capture one pointer edge update."""

    def __init__(self) -> None:
        """Initialize update counting."""

        self.update_count = 0
        self.direction = 0

    def update_for_pointer(self, _position: QPoint) -> None:
        """Record one autoscroll update."""

        self.update_count += 1


class _Geometry:
    """Publish immutable geometry counts for diagnostics."""

    state = PromptReorderInteractionGeometryState()


class _CoordinateMap:
    """Map global coordinates without owner lookups."""

    def __init__(self) -> None:
        """Initialize call counting."""

        self.call_count = 0

    def __call__(self, point: QPoint) -> QPoint:
        """Return a deterministic local offset."""

        self.call_count += 1
        return point - QPoint(2, 3)


def test_pointer_move_rejects_stale_segment_without_followup_work() -> None:
    """A stale region event must not enter the pointer hot path."""

    owner, intents, proxy, target, autoscroll, coordinate_map, metrics, _ = _owner()

    owner.move(9, QPoint(20, 30))

    assert intents.published == []
    assert proxy.move_count == 0
    assert target.positions == []
    assert autoscroll.update_count == 0
    assert coordinate_map.call_count == 0
    assert metrics.snapshot().drag_move_count == 0


def test_pointer_move_runs_one_unsampled_bounded_transition() -> None:
    """Ordinary movement must perform one proxy, target, and autoscroll update."""

    owner, intents, proxy, target, autoscroll, coordinate_map, metrics, diagnostics = (
        _owner(active_segment_index=3)
    )

    owner.move(3, QPoint(20, 30))

    assert len(intents.published) == 1
    assert proxy.move_count == 1
    assert target.positions == [QPointF(18.0, 27.0)]
    assert autoscroll.update_count == 1
    assert coordinate_map.call_count == 1
    snapshot = metrics.snapshot()
    assert snapshot.drag_move_count == 1
    assert snapshot.pointer_loop_depth == 0
    assert diagnostics.events == []
    assert diagnostics.slow_checks == 1


def _owner(
    *,
    active_segment_index: int | None = None,
) -> tuple[
    PromptReorderPointerMoveOwner,
    _Intents,
    _DragProxy,
    _TargetTransition,
    _Autoscroll,
    _CoordinateMap,
    PromptReorderInteractionMetricsOwner,
    _Diagnostics,
]:
    """Return one owner and its observable hot-path collaborators."""

    gesture = PromptReorderGestureController()
    if active_segment_index is not None:
        gesture.begin_pointer_drag(
            segment_index=active_segment_index,
            global_position=QPoint(),
        )
    intents = _Intents()
    proxy = _DragProxy()
    target = _TargetTransition()
    autoscroll = _Autoscroll()
    coordinate_map = _CoordinateMap()
    metrics = PromptReorderInteractionMetricsOwner()
    metrics.begin_gesture(11)
    diagnostics = _Diagnostics()
    owner = PromptReorderPointerMoveOwner(
        gesture=gesture,
        intents=cast(PromptReorderInteractionIntentOwner, intents),
        metrics=metrics,
        telemetry=cast(PromptReorderTelemetry, _Telemetry()),
        diagnostics=cast(PromptReorderInteractionDiagnosticsOwner, diagnostics),
        drag_proxy=cast(PromptReorderDragProxyVisualOwner, proxy),
        target_transition=cast(PromptReorderPointerTargetTransitionOwner, target),
        autoscroll=cast(PromptReorderAutoscrollOwner, autoscroll),
        geometry=cast(PromptReorderInteractionGeometry, _Geometry()),
        map_global_to_overlay=coordinate_map,
    )
    return (
        owner,
        intents,
        proxy,
        target,
        autoscroll,
        coordinate_map,
        metrics,
        diagnostics,
    )
