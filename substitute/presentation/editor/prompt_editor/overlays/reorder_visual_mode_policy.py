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

"""Select reorder visual mode from one immutable state generation."""

from __future__ import annotations

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderDropTarget,
    PromptReorderLayoutView,
)

from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)


def reorder_has_changed(state: PromptReorderInteractionGeometryState) -> bool:
    """Return whether prospective order differs from the original session."""

    return state.current_reorder_state != state.original_reorder_state


def painted_reorder_preview_layout(
    state: PromptReorderInteractionGeometryState,
    *,
    active_segment_index: int | None,
    dragged_segment_index: int | None,
    active_drop_target: PromptReorderDropTarget | None,
) -> PromptReorderLayoutView | None:
    """Return the layout represented by prepared preview painting."""

    if dragged_segment_index is not None:
        return state.preview_layout_view
    if active_segment_index is not None and active_drop_target is not None:
        return state.current_layout_view
    if reorder_has_changed(state):
        return state.current_layout_view
    return None


__all__ = ["painted_reorder_preview_layout", "reorder_has_changed"]
