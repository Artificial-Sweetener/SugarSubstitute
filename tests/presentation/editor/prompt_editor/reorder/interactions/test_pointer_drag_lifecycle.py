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

"""Verify bounded rejection at pointer drag lifecycle ownership boundaries."""

from __future__ import annotations

from typing import TypeVar, cast

from PySide6.QtCore import QPoint

from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_autoscroll import (
    PromptReorderAutoscrollOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_drag_proxy_visual_owner import (
    PromptReorderDragProxyVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_drop_commit_diagnostics import (
    PromptReorderDropCommitDiagnostics,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_held_drag_context import (
    PromptReorderHeldDragContextOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_intents import (
    PromptReorderInteractionIntentOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_paint import (
    PromptReorderLandingPaintOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_live_visual_owner import (
    PromptReorderLiveVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_performance_counters import (
    PromptReorderPerformanceCountersOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_drag_completion_owner import (
    PromptReorderPointerDragCompletionOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_drag_start_owner import (
    PromptReorderPointerDragStartOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_region_visual_owner import (
    PromptReorderPointerRegionVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_regions import (
    PromptReorderPointerRegions,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_target_transition import (
    PromptReorderPointerTargetTransitionOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_layout_transition_owner import (
    PromptReorderPreviewLayoutTransitionOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_visual_owner import (
    PromptReorderPreviewVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_render_publication_owner import (
    PromptReorderRenderPublicationOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_mode import (
    PromptReorderVisualModeOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_session import (
    PromptReorderVisualSessionOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)

_Owner = TypeVar("_Owner")


class _UnexpectedAccess:
    """Fail if a rejected lifecycle event touches another collaborator."""

    def __getattr__(self, name: str) -> object:
        """Reject every collaborator access."""

        raise AssertionError(f"unexpected lifecycle collaborator access: {name}")


def test_drag_start_rejects_duplicate_threshold_crossing_without_work() -> None:
    """An active drag must reject another start before reading geometry."""

    gesture = PromptReorderGestureController()
    gesture.begin_pointer_drag(segment_index=3, global_position=QPoint(10, 20))
    owner = _start_owner(gesture)

    owner.start(
        3,
        global_position=QPoint(12, 24),
        press_global_position=QPoint(10, 20),
    )

    assert gesture.state.dragged_segment_index == 3
    assert gesture.state.last_drag_global_position == QPoint(10, 20)


def test_drag_end_rejects_stale_region_release_without_work() -> None:
    """A stale region release must not enter the completion transition."""

    gesture = PromptReorderGestureController()
    gesture.begin_pointer_drag(segment_index=3, global_position=QPoint(10, 20))
    owner = _completion_owner(gesture)

    owner.end(9)

    assert gesture.state.dragged_segment_index == 3
    assert gesture.state.last_drag_global_position == QPoint(10, 20)


def _start_owner(
    gesture: PromptReorderGestureController,
) -> PromptReorderPointerDragStartOwner:
    """Build a drag-start owner whose unused collaborators fail on access."""

    return PromptReorderPointerDragStartOwner(
        geometry=_unreachable(PromptReorderInteractionGeometry),
        gesture=gesture,
        visual_mode=_unreachable(PromptReorderVisualModeOwner),
        live_visuals=_unreachable(PromptReorderLiveVisualOwner),
        intents=_unreachable(PromptReorderInteractionIntentOwner),
        metrics=_unreachable(PromptReorderInteractionMetricsOwner),
        performance=_unreachable(PromptReorderPerformanceCountersOwner),
        animation=_unreachable(PromptReorderAnimationPresentationOwner),
        autoscroll=_unreachable(PromptReorderAutoscrollOwner),
        diagnostics=_unreachable(PromptReorderInteractionDiagnosticsOwner),
        visual_session=_unreachable(PromptReorderVisualSessionOwner),
        landing_preview=_unreachable(PromptReorderLandingPaintOwner),
        drop_diagnostics=_unreachable(PromptReorderDropCommitDiagnostics),
        held_context=_unreachable(PromptReorderHeldDragContextOwner),
        drag_proxy=_unreachable(PromptReorderDragProxyVisualOwner),
        preview_layout=_unreachable(PromptReorderPreviewLayoutTransitionOwner),
        target_transition=_unreachable(PromptReorderPointerTargetTransitionOwner),
        pointer_regions=_unreachable(PromptReorderPointerRegionVisualOwner),
        render=_unreachable(PromptReorderRenderPublicationOwner),
        map_global_to_overlay=_unexpected_point,
        preview_layout_changed=_unexpected_callback,
    )


def _completion_owner(
    gesture: PromptReorderGestureController,
) -> PromptReorderPointerDragCompletionOwner:
    """Build a completion owner whose unused collaborators fail on access."""

    return PromptReorderPointerDragCompletionOwner(
        geometry=_unreachable(PromptReorderInteractionGeometry),
        gesture=gesture,
        visual_mode=_unreachable(PromptReorderVisualModeOwner),
        live_visuals=_unreachable(PromptReorderLiveVisualOwner),
        preview_visuals=_unreachable(PromptReorderPreviewVisualOwner),
        intents=_unreachable(PromptReorderInteractionIntentOwner),
        metrics=_unreachable(PromptReorderInteractionMetricsOwner),
        autoscroll=_unreachable(PromptReorderAutoscrollOwner),
        animation=_unreachable(PromptReorderAnimationPresentationOwner),
        landing_preview=_unreachable(PromptReorderLandingPaintOwner),
        drop_diagnostics=_unreachable(PromptReorderDropCommitDiagnostics),
        held_context=_unreachable(PromptReorderHeldDragContextOwner),
        drag_proxy=_unreachable(PromptReorderDragProxyVisualOwner),
        preview_layout=_unreachable(PromptReorderPreviewLayoutTransitionOwner),
        pointer_regions=_unreachable(PromptReorderPointerRegionVisualOwner),
        region_widgets=_unreachable(PromptReorderPointerRegions),
        render=_unreachable(PromptReorderRenderPublicationOwner),
        diagnostics=_unreachable(PromptReorderInteractionDiagnosticsOwner),
        performance=_unreachable(PromptReorderPerformanceCountersOwner),
        visual_session=_unreachable(PromptReorderVisualSessionOwner),
        preview_layout_changed=_unexpected_callback,
    )


def _unreachable(owner_type: type[_Owner]) -> _Owner:
    """Return a typed collaborator that fails if the owner reads it."""

    del owner_type
    return cast(_Owner, _UnexpectedAccess())


def _unexpected_point(_point: QPoint) -> QPoint:
    """Fail if a rejected lifecycle event maps a coordinate."""

    raise AssertionError("unexpected lifecycle coordinate mapping")


def _unexpected_callback() -> None:
    """Fail if a rejected lifecycle event publishes a preview change."""

    raise AssertionError("unexpected lifecycle preview publication")
