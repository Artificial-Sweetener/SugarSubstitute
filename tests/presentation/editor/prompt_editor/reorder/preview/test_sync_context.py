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

"""Verify reorder preview-sync context publication below preview scheduling."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TypedDict

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_models import (
    PromptReorderInitialShadowSyncResult,
    PromptReorderLandingShadowRequest,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_sync_context import (
    PromptReorderPreviewSyncContextOwner,
    PromptReorderPreviewSyncIdentifiers,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
    PromptReorderPlacementSnapshot,
)


@dataclass(slots=True)
class _Geometry:
    """Publish state and capture active-placement updates."""

    state: PromptReorderInteractionGeometryState
    active_placement: PromptReorderPlacementGeometry | None = None

    def set_active_placement(
        self,
        placement: PromptReorderPlacementGeometry | None,
    ) -> None:
        """Capture the selected placement."""

        self.active_placement = placement


@dataclass(frozen=True, slots=True)
class _GestureState:
    """Publish one dragged segment."""

    dragged_segment_index: int | None


@dataclass(slots=True)
class _Gesture:
    """Expose one gesture generation."""

    state: _GestureState


@dataclass(frozen=True, slots=True)
class _Metrics:
    """Expose deterministic scheduling identifiers."""

    gesture_id: int | None
    event_id: int | None
    pointer_loop_active: bool


@dataclass(slots=True)
class _LandingRequest:
    """Count landing-request construction."""

    request: PromptReorderLandingShadowRequest
    build_count: int = 0

    def build(self) -> PromptReorderLandingShadowRequest:
        """Return the configured request."""

        self.build_count += 1
        return self.request


@dataclass(slots=True)
class _LandingVisual:
    """Return one configured initial-shadow result."""

    result: PromptReorderInitialShadowSyncResult
    query_count: int = 0

    def should_flush_initial_landing_shadow_sync(
        self,
        request: PromptReorderLandingShadowRequest,
        *,
        base_drag_layout_available: bool,
    ) -> PromptReorderInitialShadowSyncResult:
        """Return the configured decision and count the query."""

        assert request is not None
        assert base_drag_layout_available
        self.query_count += 1
        result = self.result
        if result.should_flush:
            self.result = PromptReorderInitialShadowSyncResult(
                False,
                result.active_placement,
            )
        return result


class _Dependencies(TypedDict):
    """Describe the explicit callbacks consumed by preview-sync tests."""

    geometry_state: Callable[[], PromptReorderInteractionGeometryState]
    set_active_placement: Callable[[PromptReorderPlacementGeometry | None], None]
    dragged_segment_index: Callable[[], int | None]
    identifiers: Callable[[], PromptReorderPreviewSyncIdentifiers]
    build_landing_request: Callable[[], PromptReorderLandingShadowRequest]
    initial_shadow_sync: Callable[
        [PromptReorderLandingShadowRequest, bool],
        PromptReorderInitialShadowSyncResult,
    ]


def _dependencies(
    *,
    geometry: _Geometry,
    gesture: _Gesture,
    metrics: _Metrics,
    landing_request: _LandingRequest,
    landing_visual: _LandingVisual,
) -> _Dependencies:
    """Bind focused test doubles to preview-sync callback dependencies."""

    def initial_shadow_sync(
        request: PromptReorderLandingShadowRequest,
        base_drag_layout_available: bool,
    ) -> PromptReorderInitialShadowSyncResult:
        """Delegate the named initial-shadow decision to the test double."""

        return landing_visual.should_flush_initial_landing_shadow_sync(
            request,
            base_drag_layout_available=base_drag_layout_available,
        )

    return {
        "geometry_state": lambda: geometry.state,
        "set_active_placement": geometry.set_active_placement,
        "dragged_segment_index": lambda: gesture.state.dragged_segment_index,
        "identifiers": lambda: PromptReorderPreviewSyncIdentifiers(
            gesture_id=metrics.gesture_id,
            event_id=metrics.event_id,
            pointer_active=metrics.pointer_loop_active,
        ),
        "build_landing_request": landing_request.build,
        "initial_shadow_sync": initial_shadow_sync,
    }


def test_keyboard_context_skips_drag_geometry_and_landing_queries() -> None:
    """A keyboard-only session should publish identifiers without drag work."""

    state = _state(base_drag_ready=True)
    landing_request = _LandingRequest(_landing_request())
    landing_visual = _LandingVisual(PromptReorderInitialShadowSyncResult(False, None))
    context = PromptReorderPreviewSyncContextOwner(
        **_dependencies(
            geometry=_Geometry(state),
            gesture=_Gesture(_GestureState(None)),
            metrics=_Metrics(4, 7, False),
            landing_request=landing_request,
            landing_visual=landing_visual,
        ),
    ).snapshot()

    assert context.gesture_id == 4
    assert context.event_id == 7
    assert context.pointer_active is False
    assert context.dragged_segment_index is None
    assert context.base_drag_layout_ready is True
    assert context.requires_immediate_drag_geometry is False
    assert context.requires_initial_landing_shadow is False
    assert landing_request.build_count == 0
    assert landing_visual.query_count == 0


def test_pointer_context_requests_geometry_and_consumes_first_shadow_once() -> None:
    """An unprepared pointer drag should publish both immediate requirements."""

    geometry = _Geometry(_state(base_drag_ready=True))
    landing_request = _LandingRequest(_landing_request())
    landing_visual = _LandingVisual(PromptReorderInitialShadowSyncResult(True, None))
    owner = PromptReorderPreviewSyncContextOwner(
        **_dependencies(
            geometry=geometry,
            gesture=_Gesture(_GestureState(0)),
            metrics=_Metrics(11, 13, True),
            landing_request=landing_request,
            landing_visual=landing_visual,
        ),
    )

    context = owner.snapshot()
    subsequent_context = owner.snapshot()

    assert context.pointer_active is True
    assert context.dragged_segment_index == 0
    assert context.base_drag_layout_ready is True
    assert context.requires_immediate_drag_geometry is True
    assert context.requires_initial_landing_shadow is True
    assert subsequent_context.requires_initial_landing_shadow is False
    assert landing_request.build_count == 2
    assert landing_visual.query_count == 2


def test_pointer_context_without_base_layout_skips_landing_queries() -> None:
    """A pointer drag cannot request placement work before base layout exists."""

    landing_request = _LandingRequest(_landing_request())
    landing_visual = _LandingVisual(PromptReorderInitialShadowSyncResult(True, None))
    context = PromptReorderPreviewSyncContextOwner(
        **_dependencies(
            geometry=_Geometry(_state(base_drag_ready=False)),
            gesture=_Gesture(_GestureState(0)),
            metrics=_Metrics(2, 3, True),
            landing_request=landing_request,
            landing_visual=landing_visual,
        ),
    ).snapshot()

    assert context.base_drag_layout_ready is False
    assert context.requires_immediate_drag_geometry is False
    assert context.requires_initial_landing_shadow is False
    assert landing_request.build_count == 0
    assert landing_visual.query_count == 0


def test_pointer_context_with_prepared_placements_needs_no_geometry_rebuild() -> None:
    """Prepared placement geometry should suppress only the geometry requirement."""

    state = _state(base_drag_ready=True)
    state = replace(state, placement_snapshot=_placement_snapshot())
    landing_visual = _LandingVisual(PromptReorderInitialShadowSyncResult(False, None))
    context = PromptReorderPreviewSyncContextOwner(
        **_dependencies(
            geometry=_Geometry(state),
            gesture=_Gesture(_GestureState(0)),
            metrics=_Metrics(2, 3, True),
            landing_request=_LandingRequest(_landing_request()),
            landing_visual=landing_visual,
        ),
    ).snapshot()

    assert context.requires_immediate_drag_geometry is False
    assert context.requires_initial_landing_shadow is False
    assert landing_visual.query_count == 1


def _state(*, base_drag_ready: bool) -> PromptReorderInteractionGeometryState:
    """Return one application-backed interaction generation."""

    service = PromptDocumentService()
    document = service.build_document_view("alpha, beta")
    session = service.build_reorder_session_view(document)
    return PromptReorderInteractionGeometryState(
        document_view=document,
        current_layout_view=session.layout_view,
        base_drag_layout_view=session.layout_view if base_drag_ready else None,
        current_reorder_state=session.reorder_state,
        base_drag_reorder_state=session.reorder_state if base_drag_ready else None,
        ordered_segment_indices=(0, 1),
    )


def _landing_request() -> PromptReorderLandingShadowRequest:
    """Return a minimal request unused by the focused fake."""

    return PromptReorderLandingShadowRequest(
        gesture_id=1,
        event_id=2,
        dragged_segment_index=0,
        active_target=None,
        active_placement=None,
        dragged_segment=None,
        content_rect=QRectF(),
        overlay_rect=QRectF(),
        preview_layout_active=False,
        preview_snapshot_available=False,
        preview_visual_count=0,
        landing_geometry=None,
        target_visual=None,
        preview_geometry_target_identity=None,
        expected_preview_target_identity=None,
        preview_target_identity_matches=False,
    )


def _placement_snapshot() -> PromptReorderPlacementSnapshot:
    """Return a non-empty placement snapshot from the production value owner."""

    placement = PromptReorderPlacementGeometry(
        placement_id=PromptReorderPlacementId(
            target_kind="line",
            row_index=0,
            insertion_index=0,
            gap_index=None,
            blank_line_index=None,
            visual_line_index=0,
            ordinal=0,
        ),
        target=PromptLineDropTarget(row_index=0, insertion_index=0),
        hit_rect=QRectF(),
        insertion_anchor_rect=QRectF(),
        visual_line_rect=QRectF(),
        expected_landing_rect=None,
        source_before=None,
        source_after=None,
    )
    return PromptReorderPlacementSnapshot(
        placements=(placement,),
        visual_line_count=1,
        layout_width=100.0,
        content_height=20.0,
    )
