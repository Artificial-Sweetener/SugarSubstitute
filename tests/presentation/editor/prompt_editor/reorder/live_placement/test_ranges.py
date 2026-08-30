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

"""Verify provisional reorder geometry uses source-owned gap ranges."""

from __future__ import annotations

from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.reorder.drop import PromptReorderDropService
from substitute.application.prompt_editor.reorder.projection import (
    PromptReorderProjectionService,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_live_placement import (
    live_gap_ranges_for_layout,
)


def test_live_gap_ranges_skip_regional_boundaries() -> None:
    """Map ordinary gaps to their source rows when regional rows intervene."""

    source = (
        "tag0, tag1\n"
        "[SEP]\n"
        "tag2, tag3\n"
        "[SEP]\n"
        "tag4,\n"
        "tag5,\n"
        "[SEP]\n"
        "tag6,\n\n\n"
        "tag7,\n"
        "[SEP]\n"
        "tag8,\n"
        "[SEP]\n"
        "tag9,"
    )
    projector = PromptDocumentProjector()
    document = projector.build_document_view(source)
    session = PromptReorderProjectionService(
        document_projector=projector
    ).build_reorder_session_view(document)
    base = PromptReorderDropService(document_projector=projector).build_base_drag_state(
        document,
        session.reorder_state,
        current_layout_view=session.layout_view,
        dragged_segment_index=9,
    )

    ranges = live_gap_ranges_for_layout(
        source,
        base.layout_view,
        {chip.index: chip for chip in session.chips},
    )

    assert ranges is not None
    assert tuple(source[start:end] for start, end in ranges.values()) == (
        ",\n",
        ",\n\n\n",
    )
    assert ranges[1][0] == source.index(",\n\n\n")
