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

"""Resolve Qt colors from the active application semantic palette."""

from __future__ import annotations

from PySide6.QtGui import QColor

try:
    from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
        isDarkTheme,
        themeColor,
    )
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return False

    def themeColor() -> QColor:
        """Return a stable accent color for lightweight test stubs."""

        return QColor("#009faa")


from substitute.application.appearance import (
    AppearanceErrorColorMode,
    AppearanceWarningColorMode,
    RgbColor,
    SemanticPalette,
    resolve_semantic_palette,
)

_warning_color_mode = AppearanceWarningColorMode.DEFAULT
_error_color_mode = AppearanceErrorColorMode.DEFAULT
_custom_warning_color: str | None = None
_custom_error_color: str | None = None


def current_semantic_palette() -> SemanticPalette:
    """Return semantic colors derived from the current Fluent theme."""

    accent = QColor(themeColor())
    return resolve_semantic_palette(
        accent=RgbColor(accent.red(), accent.green(), accent.blue()),
        dark_theme=bool(isDarkTheme()),
        warning_color_mode=_warning_color_mode,
        error_color_mode=_error_color_mode,
        custom_warning_color=_custom_warning_color,
        custom_error_color=_custom_error_color,
    )


def configure_semantic_color_overrides(
    *,
    warning_color_mode: AppearanceWarningColorMode,
    error_color_mode: AppearanceErrorColorMode,
    custom_warning_color: str | None,
    custom_error_color: str | None,
) -> None:
    """Apply process-local semantic color overrides from appearance preferences."""

    global _warning_color_mode, _error_color_mode
    global _custom_warning_color, _custom_error_color
    _warning_color_mode = warning_color_mode
    _error_color_mode = error_color_mode
    _custom_warning_color = custom_warning_color
    _custom_error_color = custom_error_color


def semantic_error_color(*, alpha: int | None = None) -> QColor:
    """Return the current accent-derived semantic error foreground as a Qt color."""

    color = _qcolor_from_rgb(current_semantic_palette().error_foreground)
    if alpha is not None:
        color.setAlpha(max(0, min(255, alpha)))
    return color


def semantic_warning_color(*, alpha: int | None = None) -> QColor:
    """Return the current accent-derived semantic warning foreground as a Qt color."""

    color = _qcolor_from_rgb(current_semantic_palette().warning_foreground)
    if alpha is not None:
        color.setAlpha(max(0, min(255, alpha)))
    return color


def legible_text_color_for_background(background: QColor) -> QColor:
    """Return black or white text with better contrast on the background color."""

    luminance = (
        0.2126 * background.redF()
        + 0.7152 * background.greenF()
        + 0.0722 * background.blueF()
    )
    return QColor("#000000") if luminance > 0.58 else QColor("#ffffff")


def _qcolor_from_rgb(color: RgbColor) -> QColor:
    """Return a Qt color for one toolkit-independent RGB value."""

    return QColor(color.red, color.green, color.blue)


__all__ = [
    "current_semantic_palette",
    "configure_semantic_color_overrides",
    "legible_text_color_for_background",
    "semantic_error_color",
    "semantic_warning_color",
]
