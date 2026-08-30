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

"""Contract tests for token-aware projection layout geometry and hit testing."""

from __future__ import annotations


import pytest

from PySide6.QtGui import QColor

from tests.support.prompt_editor.projection_layout_support import (
    projection_document_for as _projection_for,
    projection_layout_for as _layout_for,
)

from .support import (
    _layout_geometry_signature,
)

_REGION_TEXT_COLOR = QColor(222, 223, 224)


@pytest.mark.parametrize(
    ("previous_text", "next_text", "expected_first_line"),
    (
        (
            "tag00\n[SEP]\nred, blue, green",
            "tag00\n[SEP]\nblue, green",
            0,
        ),
        (
            "tag00\n[SEP]\n[SEP]\nred, blue, green",
            "tag00\n[SEP]\n[SEP]\nblue, green",
            2,
        ),
        (
            "[SEP]\nred, blue, green",
            "[SEP]\nblue, green",
            0,
        ),
    ),
    ids=("single", "adjacent", "leading"),
)
def test_projection_layout_reflow_restarts_before_caretless_separator_row(
    previous_text: str,
    next_text: str,
    expected_first_line: int,
) -> None:
    """Canonical recovery should include the text line hosting a separator edge."""

    edit_start = previous_text.index("red")
    edit_end = edit_start + len("red, ")
    incremental_layout, _projection = _layout_for(previous_text)
    next_document_view, next_projection = _projection_for(next_text)
    full_layout, _full_projection = _layout_for(next_text)

    result = incremental_layout.set_projection_after_source_edit(
        next_projection,
        prompt_document_view=next_document_view,
        edit_start=edit_start,
        edit_end=edit_end,
        replacement_text="",
    )

    assert result.first_reflowed_line_index == expected_first_line
    assert _layout_geometry_signature(incremental_layout) == _layout_geometry_signature(
        full_layout
    )


def test_projection_layout_vertical_navigation_crosses_separator_rows() -> None:
    """Vertical navigation should treat non-caret separator rows as line breaks."""

    text = "alpha\n[SEP]\nbravo"
    layout, projection = _layout_for(text)
    global_position = text.index("alpha") + 3
    regional_position = text.index("bravo") + 3
    regional_state = projection.caret_map.state_for_source_position(regional_position)
    regional_rect = layout.frame.geometry.caret.cursor_rect(
        regional_state, scroll_offset=0.0
    )

    upward_target = layout.frame.geometry.caret.vertical_caret_target(
        regional_state,
        direction=-1,
        preferred_x=regional_rect.center().x(),
    )

    assert upward_target is not None
    assert upward_target.state.source_position == global_position

    global_state = projection.caret_map.state_for_source_position(global_position)
    global_rect = layout.frame.geometry.caret.cursor_rect(
        global_state, scroll_offset=0.0
    )
    downward_target = layout.frame.geometry.caret.vertical_caret_target(
        global_state,
        direction=1,
        preferred_x=global_rect.center().x(),
    )

    assert downward_target is not None
    assert downward_target.state.source_position == regional_position
