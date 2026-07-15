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

"""Tests for cube stack tab presentation text policy."""

from __future__ import annotations

from substitute.application.cubes import build_cube_tab_presentation


def test_cube_tab_presentation_formats_version_and_pack() -> None:
    """Canonical cube ids should display version and repository pack only."""

    presentation = build_cube_tab_presentation(
        alias="Text to Image",
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        version="1.1.1",
    )

    assert presentation.primary_text == "Text to Image"
    assert presentation.secondary_text == "v1.1.1 · base-cubes"
    assert presentation.tooltip_text == "Text to Image"


def test_cube_tab_presentation_uses_pack_for_target_model_paths() -> None:
    """Target-model folders should not replace the source pack label."""

    presentation = build_cube_tab_presentation(
        alias="SDXL/Image to Image",
        cube_id="Artificial-Sweetener/Base-Cubes/SDXL/Image to Image.cube",
        version="1.0.0",
    )

    assert presentation.primary_text == "SDXL/Image to Image"
    assert presentation.secondary_text == "v1.0.0 · base-cubes"


def test_cube_tab_presentation_uses_local_namespace_for_target_model_paths() -> None:
    """Local target-model cubes should show the local namespace, not the target."""

    presentation = build_cube_tab_presentation(
        alias="SDXL/Text to Image",
        cube_id="local/personal/SDXL/Text to Image.cube",
        version="1.0.0",
    )

    assert presentation.secondary_text == "v1.0.0 · personal"


def test_cube_tab_presentation_preserves_prefixed_versions() -> None:
    """Version text that already starts with v should not be double-prefixed."""

    presentation = build_cube_tab_presentation(
        alias="Inpaint",
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        version="v2.0.0",
    )

    assert presentation.secondary_text == "v2.0.0 · base-cubes"


def test_cube_tab_presentation_normalizes_pack_segment() -> None:
    """Pack names should use compact lowercase hyphenated text."""

    spaced = build_cube_tab_presentation(
        alias="Cube",
        cube_id="Artificial-Sweetener/My Pack/Cube.cube",
        version="1.0.0",
    )
    underscored = build_cube_tab_presentation(
        alias="Cube",
        cube_id="Org/base_cubes/Cube.cube",
        version="1.0.0",
    )

    assert spaced.secondary_text == "v1.0.0 · my-pack"
    assert underscored.secondary_text == "v1.0.0 · base-cubes"


def test_cube_tab_presentation_omits_missing_parts() -> None:
    """Missing version or pack metadata should leave a clean metadata row."""

    pack_only = build_cube_tab_presentation(
        alias="Cube",
        cube_id="Artificial-Sweetener/Base-Cubes/Cube.cube",
        version="",
    )
    version_only = build_cube_tab_presentation(
        alias="Cube",
        cube_id="Cube.cube",
        version="1.0.0",
    )
    empty = build_cube_tab_presentation(alias="Cube", cube_id="", version="")

    assert pack_only.secondary_text == "base-cubes"
    assert version_only.secondary_text == "v1.0.0"
    assert empty.secondary_text == ""
