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

"""Derive reusable semantic colors from the active appearance accent."""

from __future__ import annotations

from colorsys import hsv_to_rgb, rgb_to_hsv
from substitute.domain.appearance import (
    AppearanceErrorColorMode,
    AppearanceWarningColorMode,
    RgbColor,
    SemanticPalette,
)

_WARNING_HUE_OFFSET_DEGREES = 120.0
_ERROR_HUE_OFFSET_DEGREES = 240.0
_LIGHT_BACKGROUND = RgbColor(255, 255, 255)
_DARK_BACKGROUND = RgbColor(31, 31, 31)
_MINIMUM_TEXT_CONTRAST = 4.5
_FLUENT_YELLOW_LIGHT = RgbColor.from_hex("#8A6D00")
_FLUENT_YELLOW_DARK = RgbColor.from_hex("#FCE100")
_FLUENT_RED_LIGHT = RgbColor.from_hex("#C42B1C")
_FLUENT_RED_DARK = RgbColor.from_hex("#FF99A4")


def derive_semantic_palette(
    *,
    accent: RgbColor,
    dark_theme: bool,
) -> SemanticPalette:
    """Return semantic colors derived from one runtime accent color."""

    return resolve_semantic_palette(
        accent=accent,
        dark_theme=dark_theme,
        warning_color_mode=AppearanceWarningColorMode.DEFAULT,
        error_color_mode=AppearanceErrorColorMode.DEFAULT,
        custom_warning_color=None,
        custom_error_color=None,
    )


def resolve_semantic_palette(
    *,
    accent: RgbColor,
    dark_theme: bool,
    warning_color_mode: AppearanceWarningColorMode = (
        AppearanceWarningColorMode.DEFAULT
    ),
    error_color_mode: AppearanceErrorColorMode = AppearanceErrorColorMode.DEFAULT,
    custom_warning_color: str | None = None,
    custom_error_color: str | None = None,
) -> SemanticPalette:
    """Return semantic colors for derived, named, or custom appearance modes."""

    derived_warning = _derive_warning_foreground(
        accent=accent,
        dark_theme=dark_theme,
    )
    derived_error = _derive_error_foreground(
        accent=accent,
        dark_theme=dark_theme,
    )
    return SemanticPalette(
        accent=accent,
        error_foreground=_resolve_error_foreground(
            mode=error_color_mode,
            custom_error_color=custom_error_color,
            derived_error=derived_error,
            dark_theme=dark_theme,
        ),
        warning_foreground=_resolve_warning_foreground(
            mode=warning_color_mode,
            custom_warning_color=custom_warning_color,
            derived_warning=derived_warning,
            dark_theme=dark_theme,
        ),
    )


def _resolve_warning_foreground(
    *,
    mode: AppearanceWarningColorMode,
    custom_warning_color: str | None,
    derived_warning: RgbColor,
    dark_theme: bool,
) -> RgbColor:
    """Return warning foreground for one persisted warning color mode."""

    if mode is AppearanceWarningColorMode.YELLOW:
        return _FLUENT_YELLOW_DARK if dark_theme else _FLUENT_YELLOW_LIGHT
    if mode is AppearanceWarningColorMode.CUSTOM:
        return _rgb_from_optional_hex(custom_warning_color) or derived_warning
    return derived_warning


def _resolve_error_foreground(
    *,
    mode: AppearanceErrorColorMode,
    custom_error_color: str | None,
    derived_error: RgbColor,
    dark_theme: bool,
) -> RgbColor:
    """Return error foreground for one persisted error color mode."""

    if mode is AppearanceErrorColorMode.RED:
        return _FLUENT_RED_DARK if dark_theme else _FLUENT_RED_LIGHT
    if mode is AppearanceErrorColorMode.CUSTOM:
        return _rgb_from_optional_hex(custom_error_color) or derived_error
    return derived_error


def _rgb_from_optional_hex(color: str | None) -> RgbColor | None:
    """Return an RGB color from an optional hex override."""

    if color is None:
        return None
    try:
        return RgbColor.from_hex(color)
    except ValueError:
        return None


def _derive_error_foreground(
    *,
    accent: RgbColor,
    dark_theme: bool,
) -> RgbColor:
    """Return a readable error foreground using the accent hue offset rule."""

    return _derive_triadic_foreground(
        accent=accent,
        dark_theme=dark_theme,
        hue_offset=_ERROR_HUE_OFFSET_DEGREES,
    )


def _derive_warning_foreground(
    *,
    accent: RgbColor,
    dark_theme: bool,
) -> RgbColor:
    """Return a readable warning foreground from the accent's other triad corner."""

    return _derive_triadic_foreground(
        accent=accent,
        dark_theme=dark_theme,
        hue_offset=_WARNING_HUE_OFFSET_DEGREES,
    )


def _derive_triadic_foreground(
    *,
    accent: RgbColor,
    dark_theme: bool,
    hue_offset: float,
) -> RgbColor:
    """Return a readable foreground at one accent-relative triadic hue."""

    hue, saturation, value = _rgb_to_hsv_degrees(accent)
    semantic_hue = (hue + hue_offset) % 360.0
    adjusted_saturation = max(0.58, min(0.92, saturation))
    if dark_theme:
        return _readable_hsv_color(
            hue=semantic_hue,
            saturation=adjusted_saturation,
            initial_value=max(0.72, value),
            background=_DARK_BACKGROUND,
            lighten=True,
        )
    return _readable_hsv_color(
        hue=semantic_hue,
        saturation=adjusted_saturation,
        initial_value=min(0.62, value),
        background=_LIGHT_BACKGROUND,
        lighten=False,
    )


def _readable_hsv_color(
    *,
    hue: float,
    saturation: float,
    initial_value: float,
    background: RgbColor,
    lighten: bool,
) -> RgbColor:
    """Adjust HSV value until the color is legible against one background."""

    value = max(0.0, min(1.0, initial_value))
    step = 0.03 if lighten else -0.03
    for _attempt in range(32):
        candidate = _rgb_from_hsv_degrees(hue, saturation, value)
        if _contrast_ratio(candidate, background) >= _MINIMUM_TEXT_CONTRAST:
            return candidate
        value = max(0.0, min(1.0, value + step))
    return _rgb_from_hsv_degrees(hue, saturation, value)


def _rgb_to_hsv_degrees(color: RgbColor) -> tuple[float, float, float]:
    """Return HSV components with hue expressed in degrees."""

    hue, saturation, value = rgb_to_hsv(
        color.red / 255.0,
        color.green / 255.0,
        color.blue / 255.0,
    )
    return hue * 360.0, saturation, value


def _rgb_from_hsv_degrees(
    hue: float,
    saturation: float,
    value: float,
) -> RgbColor:
    """Return an RGB color from HSV components with degree hue input."""

    red, green, blue = hsv_to_rgb(
        (hue % 360.0) / 360.0,
        max(0.0, min(1.0, saturation)),
        max(0.0, min(1.0, value)),
    )
    return RgbColor(
        red=round(red * 255),
        green=round(green * 255),
        blue=round(blue * 255),
    )


def _contrast_ratio(foreground: RgbColor, background: RgbColor) -> float:
    """Return the WCAG contrast ratio for two sRGB colors."""

    foreground_luminance = _relative_luminance(foreground)
    background_luminance = _relative_luminance(background)
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(color: RgbColor) -> float:
    """Return the WCAG relative luminance for one sRGB color."""

    red = _linearized_srgb_channel(color.red)
    green = _linearized_srgb_channel(color.green)
    blue = _linearized_srgb_channel(color.blue)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _linearized_srgb_channel(channel: int) -> float:
    """Return one sRGB channel converted to linear light."""

    normalized = channel / 255.0
    if normalized <= 0.03928:
        return normalized / 12.92
    return float(((normalized + 0.055) / 1.055) ** 2.4)


__all__ = ["derive_semantic_palette", "resolve_semantic_palette"]
