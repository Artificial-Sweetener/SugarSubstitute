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

"""Tests for Qt-free cube alias display policy."""

from __future__ import annotations

from substitute.application.cubes import (
    cube_alias_body,
    split_cube_alias_prefix,
)


def test_cube_alias_body_drops_first_prefix() -> None:
    """Alias body should omit one leading model/category prefix."""

    assert cube_alias_body("SDXL/Text to Image") == "Text to Image"


def test_cube_alias_body_preserves_plain_alias() -> None:
    """Plain aliases should be displayed unchanged."""

    assert cube_alias_body("Text to Image") == "Text to Image"


def test_cube_alias_body_preserves_invalid_prefix_shapes() -> None:
    """Boundary slash aliases should not be treated as prefixed aliases."""

    assert cube_alias_body("/Text to Image") == "/Text to Image"
    assert cube_alias_body("SDXL/") == "SDXL/"


def test_cube_alias_body_drops_only_first_prefix() -> None:
    """Nested alias paths should keep the body after the first prefix."""

    assert cube_alias_body("SDXL/Refiner/Text to Image") == "Refiner/Text to Image"


def test_split_cube_alias_prefix_reports_prefix_and_body() -> None:
    """The split helper should expose card-compatible prefix and body segments."""

    parts = split_cube_alias_prefix("SDXL/Text to Image")

    assert parts.prefix == "SDXL/"
    assert parts.body == "Text to Image"
