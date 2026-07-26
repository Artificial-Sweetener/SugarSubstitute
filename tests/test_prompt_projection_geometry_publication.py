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

"""Verify immutable prompt geometry publication and owner reuse."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionSelection,
)
from tests.prompt_projection_layout_test_helpers import projection_layout_for


def test_geometry_publication_binds_focused_owners_to_one_exact_input() -> None:
    """Bind every concern owner to the same published snapshot references."""

    layout, projection = projection_layout_for("alpha,\nbeta", text_width=360.0)
    geometry = layout.frame.geometry
    geometry_input = geometry.input

    assert geometry_input.projection_document is projection
    assert geometry_input.projection_document is layout.frame.output.projection_document
    assert geometry_input.layout_snapshot is layout.frame.output.snapshot
    assert geometry_input.layout_identity == id(layout.frame.output.snapshot)
    assert all(
        owner.input is geometry_input
        for owner in (
            geometry.caret,
            geometry.hit_testing,
            geometry.selection,
            geometry.source_lines,
            geometry.tokens,
            geometry.viewport,
        )
    )


def test_geometry_queries_reuse_the_published_owners_and_source_line_cache() -> None:
    """Keep ordinary queries read-only and reuse exact source-line results."""

    layout, projection = projection_layout_for("alpha,\nbeta", text_width=360.0)
    geometry = layout.frame.geometry
    caret_state = projection.caret_map.state_for_source_position(3)
    cursor_rect = geometry.caret.cursor_rect(caret_state, scroll_offset=0.0)
    viewport_rect = QRectF(0.0, 0.0, 360.0, 240.0)

    geometry.hit_testing.hit_test(
        QPointF(cursor_rect.center()),
        scroll_offset=0.0,
    )
    geometry.selection.selection_rects(PromptProjectionSelection(0, 5))
    first_source_lines = geometry.source_lines.visible_rects(
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
    )
    second_source_lines = geometry.source_lines.visible_rects(
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
    )

    assert layout.frame.geometry is geometry
    assert layout.frame.geometry.caret is geometry.caret
    assert layout.frame.geometry.hit_testing is geometry.hit_testing
    assert layout.frame.geometry.selection is geometry.selection
    assert first_source_lines is second_source_lines


def test_layout_republication_replaces_geometry_at_the_snapshot_boundary() -> None:
    """Replace the aggregate only when layout publication replaces its snapshot."""

    layout, _projection = projection_layout_for(
        "alpha beta gamma delta",
        text_width=360.0,
    )
    previous_geometry = layout.frame.geometry
    previous_input = previous_geometry.input
    previous_snapshot = layout.frame.output.snapshot

    layout.set_text_width(120.0)

    assert layout.frame.geometry is not previous_geometry
    assert layout.frame.geometry.input is not previous_input
    assert layout.frame.output.snapshot is not previous_snapshot
    assert layout.frame.geometry.input.layout_snapshot is layout.frame.output.snapshot
    assert layout.frame.geometry.input.layout_identity == id(
        layout.frame.output.snapshot
    )
    assert previous_geometry.input.layout_snapshot is previous_snapshot
