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

"""Contract tests for Cube Library presentation icon resolution."""

from __future__ import annotations


from substitute.presentation.resources.cube_icon_factory import (
    CubeIconFactory,
)


from pytest import MonkeyPatch
from substitute.presentation.resources.cube_icon_factory import derive_cube_initials
from tests.presentation.resources.cube_icon_factory.support import (
    _alpha_bounds,
    _ensure_qapp,
    _first_opaque_rgb,
)


def test_derive_cube_initials_uses_sugarcubes_two_letter_rules() -> None:
    """Fallback initials should match current SugarCubes display behavior."""

    assert derive_cube_initials("Text to Image") == "TI"
    assert derive_cube_initials("Image to Image") == "II"
    assert derive_cube_initials("Inpaint") == "IN"
    assert derive_cube_initials("Promptmask Detailer") == "PD"
    assert derive_cube_initials("Diffusion Upscale") == "DU"


def test_derive_cube_initials_ignores_styled_model_prefix() -> None:
    """Fallback initials should use the cube name body after a styled model prefix."""

    assert derive_cube_initials("SDXL/Text to Image") == "TI"
    assert derive_cube_initials("Flux/Image to Image") == "II"
    assert derive_cube_initials("SDXL/Inpaint") == "IN"
    assert derive_cube_initials("Pony/Promptmask Detailer") == "PD"


def test_derive_cube_initials_keeps_boundary_slash_labels() -> None:
    """Fallback initials should only strip complete leading prefix tokens."""

    assert derive_cube_initials("/Text to Image") == "TI"
    assert derive_cube_initials("SDXL/") == "SD"


def test_derive_cube_initials_ignores_prefix_in_fallback_text() -> None:
    """Fallback text should use the same prefix policy when the primary label is blank."""

    assert derive_cube_initials("", fallback_text="SDXL/Text to Image") == "TI"


def test_fallback_icon_generation_returns_text_only_normalized_icon() -> None:
    """Cubes without asset descriptors should receive a normalized text icon."""

    _ensure_qapp()
    factory = CubeIconFactory()

    icon = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        display_name="Inpaint",
        icon=None,
    )

    pixmap = icon.pixmap(96, 96)
    image = pixmap.toImage()
    bounds = _alpha_bounds(image)
    assert not icon.isNull()
    assert not pixmap.isNull()
    assert bounds is not None
    min_x, min_y, max_x, max_y = bounds
    text_width = max_x - min_x + 1
    text_height = max_y - min_y + 1
    assert text_width >= 50
    assert text_height >= 40
    assert text_height <= 55
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(image.width() - 1, 0).alpha() == 0
    assert image.pixelColor(0, image.height() - 1).alpha() == 0
    assert image.pixelColor(image.width() - 1, image.height() - 1).alpha() == 0


def test_fallback_icon_normalizes_narrow_and_wide_initial_heights() -> None:
    """Fallback initials should not upscale narrow pairs more than wide pairs."""

    _ensure_qapp()
    factory = CubeIconFactory()
    text_to_image = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        display_name="Text to Image",
        icon=None,
    )
    diffusion_alpha = factory.icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Diffusion Alpha.cube",
        display_name="Diffusion Alpha",
        icon=None,
    )

    text_bounds = _alpha_bounds(text_to_image.pixmap(96, 96).toImage())
    alpha_bounds = _alpha_bounds(diffusion_alpha.pixmap(96, 96).toImage())

    assert text_bounds is not None
    assert alpha_bounds is not None
    text_height = text_bounds[3] - text_bounds[1] + 1
    alpha_height = alpha_bounds[3] - alpha_bounds[1] + 1
    assert abs(text_height - alpha_height) <= 4


def test_fallback_icon_shrinks_only_extreme_width_overflow_pairs() -> None:
    """Very wide initials should stay inside the icon footprint after shrink."""

    _ensure_qapp()
    icon = CubeIconFactory().icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Wide Wide.cube",
        display_name="Wide Wide",
        icon=None,
    )

    image = icon.pixmap(96, 96).toImage()
    bounds = _alpha_bounds(image)

    assert bounds is not None
    min_x, min_y, max_x, max_y = bounds
    assert min_x >= 2
    assert max_x <= 93
    assert max_y - min_y + 1 >= 30


def test_fallback_icon_text_color_follows_theme(monkeypatch: MonkeyPatch) -> None:
    """Fallback text should render black in light mode and white in dark mode."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    light_icon = CubeIconFactory().icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        display_name="Inpaint",
        icon=None,
    )

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: True)
    dark_icon = CubeIconFactory().icon_for_cube(
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        display_name="Inpaint",
        icon=None,
    )

    light_rgb = _first_opaque_rgb(light_icon.pixmap(96, 96).toImage())
    dark_rgb = _first_opaque_rgb(dark_icon.pixmap(96, 96).toImage())
    assert light_rgb is not None
    assert dark_rgb is not None
    assert max(light_rgb) <= 5
    assert min(dark_rgb) >= 250
