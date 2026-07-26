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

"""Publish presentation facts consumed by preview-sync scheduling."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.prompt_editor.reorder.preview_sync import (
    PromptReorderPreviewSyncContext,
)

from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from ..projection.reorder_placement_geometry import PromptReorderPlacementGeometry
from .reorder_landing_models import (
    PromptReorderInitialShadowSyncResult,
    PromptReorderLandingShadowRequest,
)


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewSyncIdentifiers:
    """Publish the constant-time interaction identity required by scheduling."""

    gesture_id: int | None
    event_id: int | None
    pointer_active: bool


class PromptReorderPreviewSyncContextOwner:
    """Build scheduling context from one presentation-state generation."""

    def __init__(
        self,
        *,
        geometry_state: Callable[[], PromptReorderInteractionGeometryState],
        set_active_placement: Callable[[PromptReorderPlacementGeometry | None], None],
        dragged_segment_index: Callable[[], int | None],
        identifiers: Callable[[], PromptReorderPreviewSyncIdentifiers],
        build_landing_request: Callable[[], PromptReorderLandingShadowRequest],
        initial_shadow_sync: Callable[
            [PromptReorderLandingShadowRequest, bool],
            PromptReorderInitialShadowSyncResult,
        ],
    ) -> None:
        """Store the focused presentation authorities consumed by the context."""

        self._geometry_state = geometry_state
        self._set_active_placement = set_active_placement
        self._dragged_segment_index = dragged_segment_index
        self._identifiers = identifiers
        self._build_landing_request = build_landing_request
        self._initial_shadow_sync = initial_shadow_sync

    def snapshot(self) -> PromptReorderPreviewSyncContext:
        """Return one existing application scheduling value."""

        geometry = self._geometry_state()
        dragged_segment_index = self._dragged_segment_index()
        base_drag_layout_ready = geometry.base_drag_layout_view is not None
        requires_immediate_drag_geometry = False
        requires_initial_landing_shadow = False
        if dragged_segment_index is not None and base_drag_layout_ready:
            placement_snapshot = geometry.placement_snapshot
            requires_immediate_drag_geometry = (
                placement_snapshot is None or not placement_snapshot.placements
            )
            landing_result = self._initial_shadow_sync(
                self._build_landing_request(), True
            )
            self._set_active_placement(landing_result.active_placement)
            requires_initial_landing_shadow = landing_result.should_flush

        identifiers = self._identifiers()
        return PromptReorderPreviewSyncContext(
            gesture_id=identifiers.gesture_id,
            event_id=identifiers.event_id,
            pointer_active=identifiers.pointer_active,
            dragged_segment_index=dragged_segment_index,
            base_drag_layout_ready=base_drag_layout_ready,
            requires_immediate_drag_geometry=requires_immediate_drag_geometry,
            requires_initial_landing_shadow=requires_initial_landing_shadow,
        )


__all__ = [
    "PromptReorderPreviewSyncContextOwner",
    "PromptReorderPreviewSyncIdentifiers",
]
