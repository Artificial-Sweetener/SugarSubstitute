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

"""Build immutable reorder commit snapshots from authoritative publications."""

from __future__ import annotations

from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCommitSnapshot,
)

from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)


def prompt_reorder_commit_snapshot(
    geometry: PromptReorderInteractionGeometryState,
    *,
    active_segment_index: int | None,
    dragged_segment_index: int | None,
    has_reordered: bool,
) -> PromptReorderCommitSnapshot:
    """Return one application snapshot without retaining presentation state."""

    return PromptReorderCommitSnapshot(
        reorder_state=geometry.current_reorder_state,
        layout_view=geometry.current_layout_view,
        ordered_chip_indices=geometry.ordered_segment_indices,
        active_segment_index=active_segment_index,
        dragged_segment_index=dragged_segment_index,
        has_reordered=has_reordered,
    )
