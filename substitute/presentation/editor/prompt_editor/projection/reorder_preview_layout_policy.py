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

"""Resolve the reorder layout represented by prepared preview geometry."""

from __future__ import annotations

from substitute.application.prompt_editor.reorder.views import PromptReorderLayoutView

from .reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)


def reorder_layout_for_painted_preview(
    state: PromptReorderInteractionGeometryState,
    *,
    dragged_segment_index: int | None,
    preview_layout_view: PromptReorderLayoutView | None,
) -> PromptReorderLayoutView | None:
    """Return the layout whose geometry should be visible for one state."""

    if dragged_segment_index is not None:
        return preview_layout_view
    if state.current_reorder_state != state.original_reorder_state:
        return state.current_layout_view
    return None


__all__ = ["reorder_layout_for_painted_preview"]
