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

"""Cover coherent reorder landing-request assembly."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QPoint, QRectF

from substitute.application.prompt_editor.document.views import PromptReorderChipView
from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderLayoutView,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_request_owner import (
    PromptReorderLandingRequestOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_visual_owner import (
    PromptReorderPreviewVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_viewport_geometry import (
    PromptReorderViewportGeometryOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_mode import (
    PromptReorderVisualModeOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_session import (
    PromptReorderVisualSessionOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_drop_targets import (
    PromptReorderDropTargetVisual,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_state import (
    reorder_overlay_position_geometry_key,
)


class _Geometry:
    """Publish replaceable immutable interaction geometry state."""

    def __init__(self, state: PromptReorderInteractionGeometryState) -> None:
        """Store the supplied state."""

        self.state = state


class _PreviewVisuals:
    """Publish a bounded prepared-preview mapping."""

    def __init__(self) -> None:
        """Publish two placeholder visual identities."""

        self.visuals_by_index = {1: object(), 2: object()}


class _Viewport:
    """Publish one stable viewport identity and count requests."""

    def __init__(self) -> None:
        """Initialize one known position key."""

        self.call_count = 0
        self.key = reorder_overlay_position_geometry_key(
            viewport_left=0,
            viewport_top=0,
            viewport_width=320,
            viewport_height=180,
            content_left=4,
            content_top=6,
            content_width=300,
            content_height=160,
            scroll_offset=12,
        )

    def position_geometry_key(self) -> object:
        """Return one stable identity and record the bounded lookup."""

        self.call_count += 1
        return self.key


def test_landing_request_reads_each_authority_once_and_preserves_identity() -> None:
    """One request should bind gesture, geometry, viewport, and session facts."""

    target = PromptLineDropTarget(row_index=0, insertion_index=1)
    target_visual = PromptReorderDropTargetVisual(
        target=target,
        hit_rect=QRectF(40.0, 20.0, 10.0, 18.0),
    )
    geometry = _Geometry(
        PromptReorderInteractionGeometryState(
            preview_layout_view=PromptReorderLayoutView(rows=(), gaps=()),
            drop_target_visuals=(target_visual,),
        )
    )
    gesture = PromptReorderGestureController()
    gesture.begin_pointer_drag(segment_index=1, global_position=QPoint(10, 10))
    gesture.set_active_drop_target(target)
    metrics = PromptReorderInteractionMetricsOwner()
    metrics.begin_gesture(7)
    visual_session = PromptReorderVisualSessionOwner()
    segment = _segment(1)
    visual_session.set_session(chips=(segment,), source_identity=None)
    viewport = _Viewport()
    owner = PromptReorderLandingRequestOwner(
        geometry=cast(PromptReorderInteractionGeometry, geometry),
        gesture=gesture,
        metrics=metrics,
        preview_visuals=cast(PromptReorderPreviewVisualOwner, _PreviewVisuals()),
        viewport=cast(PromptReorderViewportGeometryOwner, viewport),
        visual_mode=PromptReorderVisualModeOwner(
            geometry_state=lambda: geometry.state,
            gesture=gesture,
        ),
        visual_session=visual_session,
    )

    request = owner.build()

    assert request.gesture_id == 7
    assert request.event_id == 1
    assert request.dragged_segment is segment
    assert request.active_target == target
    assert request.target_visual == target_visual
    assert request.preview_visual_count == 2
    assert request.preview_layout_active is True
    assert request.content_rect == QRectF(4.0, 6.0, 300.0, 160.0)
    assert request.overlay_rect == QRectF(0.0, 0.0, 320.0, 180.0)
    assert request.expected_preview_target_identity is not None
    assert request.expected_preview_target_identity.viewport_identity is viewport.key
    assert request.preview_target_identity_matches is False
    assert viewport.call_count == 1


def _segment(index: int) -> PromptReorderChipView:
    """Return one stable visual-session chip."""

    return PromptReorderChipView(
        index=index,
        partition_index=0,
        text="beta",
        serialized_text="beta",
        display_text="beta",
        display_source_start=0,
        display_source_end=4,
        selection_start=0,
        selection_end=4,
        separator_text_after=", ",
        has_separator_after=True,
    )
