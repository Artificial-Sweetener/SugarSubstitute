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

"""Own selection of the reorder layout represented by prepared painting."""

from __future__ import annotations

from substitute.application.prompt_editor.reorder.views import PromptReorderLayoutView

from collections.abc import Callable

from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_visual_mode_policy import (
    painted_reorder_preview_layout,
    reorder_has_changed,
)


class PromptReorderVisualModeOwner:
    """Select the sole layout currently represented by reorder painting."""

    def __init__(
        self,
        *,
        geometry_state: Callable[[], PromptReorderInteractionGeometryState],
        gesture: PromptReorderGestureController,
    ) -> None:
        """Store authoritative geometry and gesture collaborators."""

        self._geometry_state = geometry_state
        self._gesture = gesture

    def has_reordered(self) -> bool:
        """Return whether prospective order differs from original session order."""

        return reorder_has_changed(self._geometry_state())

    def painted_preview_layout(self) -> PromptReorderLayoutView | None:
        """Return the layout currently represented by prepared preview painting."""

        state = self._geometry_state()
        gesture_state = self._gesture.state
        return painted_reorder_preview_layout(
            state,
            active_segment_index=gesture_state.active_segment_index,
            dragged_segment_index=gesture_state.dragged_segment_index,
            active_drop_target=gesture_state.active_drop_target,
        )

    def preview_active(self) -> bool:
        """Return whether preview painting currently owns visible chip chrome."""

        return self.painted_preview_layout() is not None


__all__ = [
    "PromptReorderVisualModeOwner",
]
