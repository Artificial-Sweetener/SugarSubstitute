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

"""Verify prompt reorder prepared visual contracts."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.overlays.reorder_prepared_visual import (
    PromptReorderPreparedVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_render_state import (
    PromptReorderViewRenderInput,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_cache import (
    PromptReorderChipVisualSnapshot,
)

from .support import (
    _style,
    _visual,
    _projection_snapshot,
)


def test_reorder_prepared_visual_owns_overlay_and_surface_atomically() -> None:
    """Prepared preview paint should publish chips and suppression together."""

    first_visual = _visual(80.0)
    first_projection = _projection_snapshot(0)
    first_snapshot = PromptReorderChipVisualSnapshot(
        segment_index=0,
        visual=first_visual,
        projection_snapshot=first_projection,
    )
    dragged_projection = _projection_snapshot(1, left=120.0, text="beta")
    dragged_snapshot = PromptReorderChipVisualSnapshot(
        segment_index=1,
        visual=_visual(120.0),
        projection_snapshot=dragged_projection,
    )

    owner = PromptReorderPreparedVisualOwner()
    publication = owner.prepare(
        PromptReorderViewRenderInput(
            visual_style=_style(),
            preview_active=True,
            live_ordered_segment_indices=(),
            preview_ordered_segment_indices=(0, 1),
            live_geometries_by_index={},
            preview_geometries_by_index={},
            live_visuals_by_index={},
            preview_visuals_by_index={0: first_visual},
            dragged_segment_index=1,
            hovered_segment_index=None,
            active_segment_index=None,
            preview_visual_snapshots_by_index={
                0: first_snapshot,
                1: dragged_snapshot,
            },
        )
    )

    assert publication.revision == 1
    assert owner.publication is publication
    assert publication.surface.mode == "preview"
    assert tuple(
        chip.segment_index for chip in publication.overlay_state.preview_chips
    ) == (0,)
    assert publication.surface.chips == ()
    assert publication.unsafe_transient_indices == ()
    assert publication.surface.suppression_snapshots_by_index == {
        0: first_projection,
        1: dragged_projection,
    }
