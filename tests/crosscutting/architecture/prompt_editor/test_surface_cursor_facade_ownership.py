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

"""Enforce focused ownership of the projection surface cursor contract."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_cursor_facade_owns_cursor_behavior() -> None:
    """Keep cursor interpretation and movement policy out of the Qt adapter."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    facade_source = (projection_root / "surface_cursor_facade.py").read_text(
        encoding="utf-8"
    )

    for ownership_marker in (
        "PromptCursorAdapter(",
        "QTextCursor.MoveMode.KeepAnchor",
        "QTextCursor.SelectionType.WordUnderCursor",
        "caret_map.state_for_source_position(",
        "prompt_word_bounds(",
        'command_name="cursor_delete_selection"',
        'command_name="cursor_insert_text"',
    ):
        assert ownership_marker in facade_source
        assert ownership_marker not in surface_source

    assert "self._cursor_facade = composition_runtime.cursor" in surface_source


def test_arrow_routing_preserves_deferred_projection_contract() -> None:
    """Keep direct arrow movement distinct from flushed cursor operations."""

    facade_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "surface_cursor_facade.py"
    ).read_text(encoding="utf-8")
    horizontal_start = facade_source.index("def move_horizontally(")
    vertical_start = facade_source.index("def move_vertically(")
    selection_start = facade_source.index("def select_by_mode(")
    arrow_block = facade_source[horizontal_start:selection_start]

    assert horizontal_start < vertical_start < selection_start
    assert "flush_pending_projection" not in arrow_block
    assert 'flush_pending_projection("move_cursor_by_operation")' in facade_source
