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

"""Publish coherent immutable facts for one reorder preview build."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderDropTarget,
)

from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from ..projection.reorder_preview_build_facts import PromptReorderPreviewBuildFacts
from .reorder_visual_mode_policy import (
    painted_reorder_preview_layout,
    reorder_has_changed,
)


class PromptReorderPreviewBuildFactsOwner:
    """Assemble preview inputs from focused immutable publications."""

    def __init__(
        self,
        *,
        geometry_state: Callable[[], PromptReorderInteractionGeometryState],
        gesture_facts: Callable[
            [], tuple[int | None, int | None, PromptReorderDropTarget | None]
        ],
        keyboard_drop_target: Callable[[], PromptReorderDropTarget | None],
    ) -> None:
        """Store the four narrow authorities needed to publish preview facts."""

        self._geometry_state = geometry_state
        self._gesture_facts = gesture_facts
        self._keyboard_drop_target = keyboard_drop_target

    def snapshot(self) -> PromptReorderPreviewBuildFacts:
        """Return one immutable preview-build generation."""

        geometry = self._geometry_state()
        active_segment_index, dragged_segment_index, active_drop_target = (
            self._gesture_facts()
        )
        has_reordered = reorder_has_changed(geometry)
        preview_layout = painted_reorder_preview_layout(
            geometry,
            active_segment_index=active_segment_index,
            dragged_segment_index=dragged_segment_index,
            active_drop_target=active_drop_target,
        )
        preview_reorder_state = None
        # Pointer state stays provisional; keyboard moves promote state before painting.
        if dragged_segment_index is not None and preview_layout is not None:
            preview_reorder_state = geometry.preview_reorder_state
        elif preview_layout is not None or has_reordered:
            preview_reorder_state = geometry.current_reorder_state

        if dragged_segment_index is not None:
            drop_target = active_drop_target
        elif has_reordered:
            drop_target = self._keyboard_drop_target()
        else:
            drop_target = None

        return PromptReorderPreviewBuildFacts(
            preview_layout_view=preview_layout,
            base_drag_layout_view=geometry.base_drag_layout_view,
            preview_reorder_state=preview_reorder_state,
            base_drag_reorder_state=geometry.base_drag_reorder_state,
            ordered_chip_indices=geometry.ordered_segment_indices,
            dragged_segment_index=dragged_segment_index,
            drop_target=drop_target,
        )


__all__ = [
    "PromptReorderPreviewBuildFactsOwner",
]
