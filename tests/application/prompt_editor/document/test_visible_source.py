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

"""Verify one prompt display mapping owns text and source boundaries together."""

from __future__ import annotations

from substitute.application.prompt_editor.document.visible_source import (
    map_prompt_source_for_display,
    visible_indices_for_source_range,
)


def test_visible_source_maps_storage_escapes_to_single_parentheses() -> None:
    """Expose one caret step per visible paren while retaining source offsets."""

    visible = map_prompt_source_for_display(r"cat \(animal\)", source_start=5)

    assert visible.display_text == "cat (animal)"
    assert tuple(visible.source_positions) == (
        5,
        6,
        7,
        8,
        9,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        19,
    )


def test_visible_source_preserves_identity_mapping_without_escapes() -> None:
    """Keep ordinary prompt text on the compact one-to-one source path."""

    visible = map_prompt_source_for_display("portrait", source_start=7)

    assert visible.display_text == "portrait"
    assert visible.source_positions == range(7, 16)


def test_source_range_touching_hidden_escape_maps_to_its_visible_glyph() -> None:
    """Select the visible parenthesis for any source overlap with its escape."""

    visible = map_prompt_source_for_display(r"\(cat\)")

    assert visible_indices_for_source_range(visible.source_positions, 0, 1) == (0, 1)
    assert visible_indices_for_source_range(visible.source_positions, 1, 2) == (0, 1)
    assert visible_indices_for_source_range(visible.source_positions, 5, 6) == (4, 5)
    assert visible_indices_for_source_range(visible.source_positions, 0, 7) == (0, 5)
