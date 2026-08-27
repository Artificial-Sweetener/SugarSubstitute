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

"""Regression tests for prompt projection Unicode and input-method behavior."""

from __future__ import annotations


import pytest

import substitute.presentation.text_coordinates as text_coordinates_module
from substitute.presentation.text_coordinates import TextCoordinateMap
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)


def test_text_coordinate_map_keeps_surrogates_and_graphemes_atomic() -> None:
    """Map Qt offsets without exposing interior surrogate or grapheme boundaries."""

    coordinates = TextCoordinateMap("A👩‍🚀é日")

    assert coordinates.utf16_length == 9
    assert coordinates.python_to_utf16(2) == 3
    assert coordinates.utf16_to_python(2) == 1
    assert coordinates.utf16_to_python(2, prefer_after=True) == 2
    assert coordinates.utf16_to_python(10_000) == len(coordinates.text)
    assert coordinates.utf16_offsets_by_python_index() == (0, 1, 3, 4, 6, 7, 8, 9)
    assert coordinates.grapheme_boundaries() == (0, 1, 4, 6, 7)
    assert coordinates.next_grapheme_boundary(1) == 4
    assert coordinates.previous_grapheme_boundary(6) == 4


def test_text_coordinate_map_resolves_graphemes_with_linear_width_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve a boundary batch with one character-width pass."""

    text = "A👩‍🚀é日" * 256
    width_call_count = 0
    original_width = text_coordinates_module._utf16_code_units  # noqa: SLF001

    def count_width(character: str) -> int:
        """Count coordinate-width work without changing its result."""

        nonlocal width_call_count
        width_call_count += 1
        return original_width(character)

    monkeypatch.setattr(
        text_coordinates_module,
        "_utf16_code_units",
        count_width,
    )

    boundaries = TextCoordinateMap(text).grapheme_boundaries()

    assert boundaries[0] == 0
    assert boundaries[-1] == len(text)
    assert width_call_count == len(text)
