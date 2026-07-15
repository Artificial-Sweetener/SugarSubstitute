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

"""Provide projection-local theme and color conversion helpers."""

from __future__ import annotations

from PySide6.QtGui import QColor
from qfluentwidgets import isDarkTheme  # type: ignore[import-untyped]

from substitute.application.appearance import RgbColor, SemanticPalette
from substitute.presentation.semantic_colors import current_semantic_palette


def scene_zebra_color() -> QColor:
    """Return the subtle alternating prompt fill color."""

    return QColor(255, 255, 255, 10) if isDarkTheme() else QColor(0, 0, 0, 8)


def semantic_palette_from_theme() -> SemanticPalette:
    """Return semantic colors derived from the current Fluent theme."""

    return current_semantic_palette()


def qcolor_from_rgb(color: RgbColor) -> QColor:
    """Return a Qt color for one presentation-neutral RGB value."""

    return QColor(color.red, color.green, color.blue)


__all__ = [
    "qcolor_from_rgb",
    "scene_zebra_color",
    "semantic_palette_from_theme",
]
