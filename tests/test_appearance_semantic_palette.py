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

"""Tests for reusable semantic palette derivation."""

from __future__ import annotations

from colorsys import rgb_to_hsv

import pytest

from substitute.application.appearance import (
    derive_semantic_palette,
    resolve_semantic_palette,
)
from substitute.domain.appearance import (
    AppearanceErrorColorMode,
    AppearanceWarningColorMode,
    RgbColor,
)


def test_semantic_palette_rotates_error_hue_from_accent() -> None:
    """Error foreground should keep the accent-derived 240 degree hue offset."""

    palette = derive_semantic_palette(
        accent=RgbColor.from_hex("#FF0000"),
        dark_theme=True,
    )

    assert _hue_degrees(palette.error_foreground) == pytest.approx(240.0, abs=1.0)


def test_semantic_palette_rotates_warning_hue_to_other_triad_corner() -> None:
    """Warning foreground should use the accent-derived 120 degree hue offset."""

    palette = derive_semantic_palette(
        accent=RgbColor.from_hex("#FF0000"),
        dark_theme=True,
    )

    assert _hue_degrees(palette.warning_foreground) == pytest.approx(120.0, abs=1.0)


def test_semantic_palette_uses_different_readable_values_by_theme() -> None:
    """Light and dark themes should share hue while using readable brightness."""

    accent = RgbColor.from_hex("#E91E63")

    light_palette = derive_semantic_palette(accent=accent, dark_theme=False)
    dark_palette = derive_semantic_palette(accent=accent, dark_theme=True)

    assert _hue_degrees(light_palette.error_foreground) == pytest.approx(
        _hue_degrees(dark_palette.error_foreground),
        abs=1.0,
    )
    assert light_palette.error_foreground != dark_palette.error_foreground
    assert light_palette.warning_foreground != dark_palette.warning_foreground
    assert light_palette.error_foreground.to_hex().startswith("#")
    assert dark_palette.error_foreground.to_hex().startswith("#")
    assert light_palette.warning_foreground.to_hex().startswith("#")
    assert dark_palette.warning_foreground.to_hex().startswith("#")


def test_semantic_palette_uses_custom_warning_and_error_overrides() -> None:
    """Custom warning/error colors should replace only their derived defaults."""

    palette = resolve_semantic_palette(
        accent=RgbColor.from_hex("#E91E63"),
        dark_theme=True,
        warning_color_mode=AppearanceWarningColorMode.CUSTOM,
        error_color_mode=AppearanceErrorColorMode.CUSTOM,
        custom_warning_color="#ffaa00",
        custom_error_color="#cc1122",
    )

    assert palette.accent == RgbColor.from_hex("#E91E63")
    assert palette.warning_foreground == RgbColor.from_hex("#FFAA00")
    assert palette.error_foreground == RgbColor.from_hex("#CC1122")


def test_semantic_palette_uses_theme_specific_yellow_and_red_modes() -> None:
    """Named yellow/red modes should use Fluent-friendly theme-specific colors."""

    light_palette = resolve_semantic_palette(
        accent=RgbColor.from_hex("#E91E63"),
        dark_theme=False,
        warning_color_mode=AppearanceWarningColorMode.YELLOW,
        error_color_mode=AppearanceErrorColorMode.RED,
    )
    dark_palette = resolve_semantic_palette(
        accent=RgbColor.from_hex("#E91E63"),
        dark_theme=True,
        warning_color_mode=AppearanceWarningColorMode.YELLOW,
        error_color_mode=AppearanceErrorColorMode.RED,
    )

    assert light_palette.warning_foreground == RgbColor.from_hex("#8A6D00")
    assert dark_palette.warning_foreground == RgbColor.from_hex("#FCE100")
    assert light_palette.error_foreground == RgbColor.from_hex("#C42B1C")
    assert dark_palette.error_foreground == RgbColor.from_hex("#FF99A4")


def test_rgb_color_rejects_invalid_hex_and_channels() -> None:
    """RGB color values should stay inside normalized sRGB bounds."""

    with pytest.raises(ValueError, match="#RRGGBB"):
        RgbColor.from_hex("E91E63")
    with pytest.raises(ValueError, match="red"):
        RgbColor(red=-1, green=0, blue=0)
    with pytest.raises(ValueError, match="blue"):
        RgbColor(red=0, green=0, blue=256)


def _hue_degrees(color: RgbColor) -> float:
    """Return one RGB color's hue in degrees for semantic color assertions."""

    hue, _saturation, _value = rgb_to_hsv(
        color.red / 255.0,
        color.green / 255.0,
        color.blue / 255.0,
    )
    return hue * 360.0
