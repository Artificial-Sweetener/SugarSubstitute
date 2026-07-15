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

"""Provide QFluent-derived colors for custom media wall painting."""

from __future__ import annotations

from PySide6.QtGui import QColor
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
    themeColor,
)

MENU_RADIUS = 5
TILE_RADIUS = 8


def media_wall_placeholder_fill() -> QColor:
    """Return the QFluent card-like fill color for empty thumbnail tiles."""

    return QColor(255, 255, 255, 13) if isDarkTheme() else QColor(255, 255, 255, 170)


def media_wall_placeholder_text() -> QColor:
    """Return a muted text color for empty thumbnail tile labels."""

    return QColor(255, 255, 255, 150) if isDarkTheme() else QColor(0, 0, 0, 150)


def media_wall_hover_border() -> QColor:
    """Return the QFluent menu/card hover border color for tiles."""

    return QColor(255, 255, 255, 90) if isDarkTheme() else QColor(0, 0, 0, 80)


def media_wall_current_border() -> QColor:
    """Return the accent-aware current tile border color."""

    color = QColor(themeColor())
    color.setAlpha(235 if isDarkTheme() else 220)
    return color


def media_wall_title_text() -> QColor:
    """Return the primary over-image title color."""

    return QColor(255, 255, 255, 235)


def media_wall_subtitle_text() -> QColor:
    """Return the secondary over-image subtitle color."""

    return QColor(255, 255, 255, 175)


def media_wall_title_edge_fade() -> QColor:
    """Return the fade color matching the bottom title vignette."""

    return QColor(0, 0, 0, 205)


__all__ = [
    "MENU_RADIUS",
    "TILE_RADIUS",
    "media_wall_current_border",
    "media_wall_hover_border",
    "media_wall_placeholder_fill",
    "media_wall_placeholder_text",
    "media_wall_subtitle_text",
    "media_wall_title_edge_fade",
    "media_wall_title_text",
]
