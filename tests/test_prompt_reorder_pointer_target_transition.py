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

"""Cover complete pointer-selected reorder target transitions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, cast

import pytest
from PySide6.QtCore import QPoint, QPointF

from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderLayoutView,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_displacement_intent import (
    ReorderDisplacementIntent,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_state import (
    PromptReorderLandingState,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_target_transition import (
    PromptReorderPointerTargetTransitionOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_mode import (
    PromptReorderVisualModeOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_pointer_hit_testing import (
    PromptReorderDropTargetResolution,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_state import (
    PromptReorderOverlayPositionGeometryKey,
)


class _Resolver:
    """Publish a deterministic target resolution."""

    def __init__(
        self,
        resolution: PromptReorderDropTargetResolution,
    ) -> None:
        """Store the next resolution."""

        self._resolution = resolution
        self.resolve_count = 0
        self.last_resolve_elapsed_ms = 0.25

    def resolve(
        self,
        local_pointer: QPointF,
    ) -> PromptReorderDropTargetResolution:
        """Return the configured result."""

        _ = local_pointer
        self.resolve_count += 1
        return self._resolution


class _Geometry:
    """Publish replaceable geometry and count preview-layout work."""

    def __init__(self, *, reject_preview: bool = False) -> None:
        """Initialize empty interaction geometry."""

        self.state = PromptReorderInteractionGeometryState()
        self.update_count = 0
        self.reject_preview = reject_preview

    def update_preview_layout(
        self,
        *,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: object | None,
        gesture_id: int | None,
        event_id: int | None,
    ) -> None:
        """Publish one deterministic preview layout."""

        _ = (
            dragged_segment_index,
            active_target,
            viewport_identity,
            gesture_id,
            event_id,
        )
        self.update_count += 1
        if self.reject_preview:
            raise ValueError("invalid preview target")
        self.state = replace(
            self.state,
            preview_layout_view=cast(PromptReorderLayoutView, object()),
            ordered_segment_indices=(0, 1),
        )

    def set_active_placement(
        self,
        placement: PromptReorderPlacementGeometry | None,
    ) -> None:
        """Publish one successfully transitioned placement."""

        self.state = replace(self.state, active_placement=placement)


class _Animation:
    """Record target-change displacement requests."""

    def __init__(self) -> None:
        """Initialize no recorded requests."""

        self.intents: list[ReorderDisplacementIntent] = []

    def record_target_change(
        self,
        intent: ReorderDisplacementIntent,
        *,
        segment_indices: Sequence[int],
        preview_active: bool,
        live_visuals_by_index: Mapping[int, PromptChipVisual],
        preview_visuals_by_index: Mapping[int, PromptChipVisual],
    ) -> None:
        """Record one complete request without visual work."""

        _ = (
            segment_indices,
            preview_active,
            live_visuals_by_index,
            preview_visuals_by_index,
        )
        self.intents.append(intent)


class _VisualSource:
    """Expose one immutable empty visual mapping."""

    @property
    def visuals_by_index(self) -> Mapping[int, PromptChipVisual]:
        """Return no visuals for transition orchestration tests."""

        return {}


class _Regions:
    """Expose stable materialized region indices."""

    @property
    def regions_by_index(self) -> Mapping[int, object]:
        """Return two semantic region identities."""

        return {0: object(), 1: object()}


class _DragProxy:
    """Count proxy stacking requests."""

    def __init__(self) -> None:
        """Initialize no requests."""

        self.raise_count = 0

    def raise_proxy(self) -> None:
        """Record one stacking request."""

        self.raise_count += 1


class _Landing:
    """Expose empty immutable landing state."""

    @property
    def publication(self) -> PromptReorderLandingState:
        """Return an empty landing publication."""

        return PromptReorderLandingState()


class _Viewport:
    """Count lazy changed-target viewport identity queries."""

    def __init__(self) -> None:
        """Initialize no viewport queries."""

        self.query_count = 0

    def position_geometry_key(self) -> PromptReorderOverlayPositionGeometryKey:
        """Return one stable viewport identity."""

        self.query_count += 1
        return PromptReorderOverlayPositionGeometryKey(
            viewport_left=0,
            viewport_top=0,
            viewport_width=320,
            viewport_height=180,
            content_left=4,
            content_top=4,
            content_width=312,
            content_height=172,
            scroll_offset=0,
        )


class _PreviewEvents:
    """Count preview-layout change publications."""

    def __init__(self) -> None:
        """Initialize no events."""

        self.emit_count = 0

    def emit_preview_layout_changed(self) -> None:
        """Record one preview-layout event."""

        self.emit_count += 1


def test_unchanged_pointer_target_performs_no_transition_or_viewport_work() -> None:
    """Same-target pointer input must remain a resolution-only fast path."""

    gesture = _active_gesture()
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    gesture.set_active_drop_target(target)
    geometry = _Geometry()
    animation = _Animation()
    proxy = _DragProxy()
    viewport = _Viewport()
    events = _PreviewEvents()
    owner = _owner(
        resolver=_Resolver(
            PromptReorderDropTargetResolution(
                target=target,
                active_placement=None,
                changed=False,
            ),
        ),
        geometry=geometry,
        gesture=gesture,
        animation=animation,
        proxy=proxy,
        viewport=viewport,
        events=events,
    )

    assert owner.update(QPointF(30.0, 20.0)) is False
    assert geometry.update_count == 0
    assert animation.intents == []
    assert proxy.raise_count == 0
    assert viewport.query_count == 0
    assert events.emit_count == 0


def test_changed_pointer_target_publishes_one_complete_transition() -> None:
    """Changed input must animate, publish geometry, stack, and emit exactly once."""

    gesture = _active_gesture()
    target = PromptLineDropTarget(row_index=1, insertion_index=1)
    geometry = _Geometry()
    animation = _Animation()
    proxy = _DragProxy()
    viewport = _Viewport()
    events = _PreviewEvents()
    owner = _owner(
        resolver=_Resolver(
            PromptReorderDropTargetResolution(
                target=target,
                active_placement=None,
                changed=True,
            ),
        ),
        geometry=geometry,
        gesture=gesture,
        animation=animation,
        proxy=proxy,
        viewport=viewport,
        events=events,
    )

    assert owner.update(QPointF(70.0, 40.0)) is True
    assert geometry.update_count == 1
    assert gesture.state.active_drop_target == target
    assert animation.intents[0].target == target
    assert animation.intents[0].held_segment_index == 1
    assert proxy.raise_count == 1
    assert viewport.query_count == 1
    assert events.emit_count == 1


def test_rejected_preview_does_not_publish_target_or_visual_transition() -> None:
    """A failed preview build must leave the last valid drag state authoritative."""

    gesture = _active_gesture()
    previous_target = PromptLineDropTarget(row_index=0, insertion_index=0)
    rejected_target = PromptLineDropTarget(row_index=99, insertion_index=0)
    gesture.set_active_drop_target(previous_target)
    geometry = _Geometry(reject_preview=True)
    animation = _Animation()
    proxy = _DragProxy()
    events = _PreviewEvents()
    owner = _owner(
        resolver=_Resolver(
            PromptReorderDropTargetResolution(
                target=rejected_target,
                active_placement=None,
                changed=True,
            ),
        ),
        geometry=geometry,
        gesture=gesture,
        animation=animation,
        proxy=proxy,
        viewport=_Viewport(),
        events=events,
    )

    with pytest.raises(ValueError, match="invalid preview target"):
        owner.update(QPointF(70.0, 40.0))

    assert gesture.state.active_drop_target == previous_target
    assert geometry.state.active_placement is None
    assert animation.intents == []
    assert proxy.raise_count == 0
    assert events.emit_count == 0


def test_changed_autoscroll_target_can_suppress_duplicate_preview_event() -> None:
    """Autoscroll settlement may apply a target without emitting a second signal."""

    gesture = _active_gesture()
    target = PromptLineDropTarget(row_index=1, insertion_index=0)
    geometry = _Geometry()
    events = _PreviewEvents()
    owner = _owner(
        resolver=_Resolver(
            PromptReorderDropTargetResolution(
                target=target,
                active_placement=None,
                changed=True,
            ),
        ),
        geometry=geometry,
        gesture=gesture,
        animation=_Animation(),
        proxy=_DragProxy(),
        viewport=_Viewport(),
        events=events,
    )

    assert (
        owner.update(
            QPointF(40.0, 80.0),
            emit_preview_changed=False,
        )
        is True
    )
    assert geometry.update_count == 1
    assert events.emit_count == 0


def _owner(
    *,
    resolver: _Resolver,
    geometry: _Geometry,
    gesture: PromptReorderGestureController,
    animation: _Animation,
    proxy: _DragProxy,
    viewport: _Viewport,
    events: _PreviewEvents,
) -> PromptReorderPointerTargetTransitionOwner:
    """Return one transition owner with production metrics and diagnostics."""

    metrics = PromptReorderInteractionMetricsOwner()
    return PromptReorderPointerTargetTransitionOwner(
        resolver=cast(Any, resolver),
        geometry=cast(Any, geometry),
        gesture=gesture,
        animation=cast(Any, animation),
        live_visuals=cast(Any, _VisualSource()),
        preview_visuals=cast(Any, _VisualSource()),
        regions=cast(Any, _Regions()),
        drag_proxy=cast(Any, proxy),
        landing=cast(Any, _Landing()),
        viewport=cast(Any, viewport),
        visual_mode=PromptReorderVisualModeOwner(
            geometry_state=lambda: geometry.state,
            gesture=gesture,
        ),
        preview_layout_changed=events.emit_preview_layout_changed,
        metrics=metrics,
        diagnostics=PromptReorderInteractionDiagnosticsOwner(
            telemetry=PromptReorderTelemetry(),
            metrics=metrics,
        ),
        telemetry=PromptReorderTelemetry(),
    )


def _active_gesture() -> PromptReorderGestureController:
    """Return one gesture with a held pointer segment."""

    gesture = PromptReorderGestureController()
    gesture.begin_pointer_drag(
        segment_index=1,
        global_position=QPoint(100, 60),
    )
    return gesture
