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

"""Define shared Fluent Settings metrics and theme-aware color helpers."""

from __future__ import annotations

from PySide6.QtCore import QMargins
from PySide6.QtGui import QColor
from qfluentwidgets.common.color import themeColor  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]

from substitute.presentation.shell.chrome_style import (
    resolved_backdrop_mode,
    windows_list_item_state_overlay_color,
    winui_card_border_color,
    winui_card_fill_color,
)

SETTINGS_CONTENT_MAX_WIDTH = 1000
SETTINGS_PAGE_HORIZONTAL_MARGIN = 24
SETTINGS_PAGE_TOP_MARGIN = 24
SETTINGS_PAGE_HEADER_TO_FIRST_GROUP_SPACING = 20
SETTINGS_PAGE_BOTTOM_MARGIN = 24

SETTINGS_NAVIGATION_WIDTH = 280
SETTINGS_NAVIGATION_ITEM_WIDTH = 260
SETTINGS_NAVIGATION_ITEM_HEIGHT = 40
SETTINGS_NAVIGATION_TOP_MARGIN = 12
SETTINGS_NAVIGATION_ITEM_SPACING = 4
SETTINGS_NAVIGATION_ICON_SIZE = 18
SETTINGS_NAVIGATION_ICON_TEXT_GAP = 14
SETTINGS_NAVIGATION_RADIUS = 5
SETTINGS_NAVIGATION_RAIL_WIDTH = 3
SETTINGS_NAVIGATION_RAIL_HEIGHT = 16

SETTINGS_CARD_MIN_WIDTH = 148
SETTINGS_CARD_MIN_HEIGHT = 68
SETTINGS_CARD_RADIUS = 6
SETTINGS_CARD_PADDING = QMargins(16, 16, 16, 16)
SETTINGS_CARD_DESCRIPTION_FONT_SIZE = 12
SETTINGS_CARD_ICON_MAX_SIZE = 20
SETTINGS_CARD_ICON_RIGHT_MARGIN = 20
SETTINGS_CARD_TEXT_CONTROL_GAP = 24
SETTINGS_CARD_TRAILING_MIN_WIDTH = 120
SETTINGS_CARD_ACTION_ICON_MAX_SIZE = 13
SETTINGS_CARD_ACTION_ICON_LEFT_MARGIN = 14
SETTINGS_CARD_VERTICAL_CONTENT_SPACING = 8
SETTINGS_CARD_WRAP_THRESHOLD = 476
SETTINGS_CARD_WRAP_NO_ICON_THRESHOLD = 286
SETTINGS_CARD_GROUP_SPACING = 4
SETTINGS_CARD_GROUP_TITLE_BOTTOM_MARGIN = 6
SETTINGS_CARD_GROUP_TOP_MARGIN = 30
SETTINGS_EXPANDER_HEADER_PADDING = QMargins(16, 16, 4, 16)
SETTINGS_EXPANDER_ITEM_PADDING = QMargins(58, 8, 44, 8)
CLICKABLE_SETTINGS_EXPANDER_ITEM_PADDING = QMargins(58, 8, 16, 8)
SETTINGS_EXPANDER_ITEM_MIN_HEIGHT = 52
SETTINGS_EXPANDER_CHEVRON_BUTTON_SIZE = 32


def qcolor_from_rgba(rgba: tuple[int, int, int, int]) -> QColor:
    """Return a ``QColor`` from one RGBA tuple."""

    red, green, blue, alpha = rgba
    return QColor(red, green, blue, alpha)


def settings_card_fill_color(widget: object | None = None) -> QColor:
    """Return the normal Settings card fill for the current shell material."""

    if isDarkTheme():
        return QColor(43, 43, 43, 255)
    if widget is not None:
        return qcolor_from_rgba(winui_card_fill_color(resolved_backdrop_mode(widget)))
    return qcolor_from_rgba(winui_card_fill_color(resolved_backdrop_mode(widget)))


def settings_card_border_color() -> QColor:
    """Return the normal Settings card border color."""

    return qcolor_from_rgba(winui_card_border_color())


def settings_card_overlay_color(*, pressed: bool, hovered: bool) -> QColor:
    """Return the hover or pressed overlay used by interactive Settings cards."""

    return windows_list_item_state_overlay_color(
        is_dark=isDarkTheme(),
        is_pressed=pressed,
        is_hovered=hovered,
    )


def settings_disabled_foreground_color() -> QColor:
    """Return the foreground color used for disabled Settings card text."""

    return QColor(255, 255, 255, 92) if isDarkTheme() else QColor(0, 0, 0, 92)


def settings_navigation_selected_fill_color() -> QColor:
    """Return the selected Settings navigation row fill."""

    return QColor(255, 255, 255, 16) if isDarkTheme() else QColor(0, 0, 0, 9)


def settings_navigation_overlay_color(*, pressed: bool, hovered: bool) -> QColor:
    """Return the hover or pressed overlay used by Settings navigation rows."""

    return windows_list_item_state_overlay_color(
        is_dark=isDarkTheme(),
        is_pressed=pressed,
        is_hovered=hovered,
    )


def settings_accent_color() -> QColor:
    """Return the active QFluent accent color."""

    return QColor(themeColor())


__all__ = [
    "SETTINGS_CARD_ACTION_ICON_LEFT_MARGIN",
    "SETTINGS_CARD_ACTION_ICON_MAX_SIZE",
    "SETTINGS_CARD_DESCRIPTION_FONT_SIZE",
    "SETTINGS_CARD_GROUP_SPACING",
    "SETTINGS_CARD_GROUP_TITLE_BOTTOM_MARGIN",
    "SETTINGS_CARD_GROUP_TOP_MARGIN",
    "SETTINGS_CARD_ICON_MAX_SIZE",
    "SETTINGS_CARD_ICON_RIGHT_MARGIN",
    "SETTINGS_CARD_MIN_HEIGHT",
    "SETTINGS_CARD_MIN_WIDTH",
    "SETTINGS_CARD_PADDING",
    "SETTINGS_CARD_RADIUS",
    "SETTINGS_CARD_TEXT_CONTROL_GAP",
    "SETTINGS_CARD_TRAILING_MIN_WIDTH",
    "SETTINGS_CARD_VERTICAL_CONTENT_SPACING",
    "SETTINGS_CARD_WRAP_NO_ICON_THRESHOLD",
    "SETTINGS_CARD_WRAP_THRESHOLD",
    "CLICKABLE_SETTINGS_EXPANDER_ITEM_PADDING",
    "SETTINGS_EXPANDER_CHEVRON_BUTTON_SIZE",
    "SETTINGS_EXPANDER_HEADER_PADDING",
    "SETTINGS_EXPANDER_ITEM_MIN_HEIGHT",
    "SETTINGS_EXPANDER_ITEM_PADDING",
    "SETTINGS_CONTENT_MAX_WIDTH",
    "SETTINGS_NAVIGATION_ICON_SIZE",
    "SETTINGS_NAVIGATION_ICON_TEXT_GAP",
    "SETTINGS_NAVIGATION_ITEM_HEIGHT",
    "SETTINGS_NAVIGATION_ITEM_SPACING",
    "SETTINGS_NAVIGATION_ITEM_WIDTH",
    "SETTINGS_NAVIGATION_RADIUS",
    "SETTINGS_NAVIGATION_RAIL_HEIGHT",
    "SETTINGS_NAVIGATION_RAIL_WIDTH",
    "SETTINGS_NAVIGATION_TOP_MARGIN",
    "SETTINGS_NAVIGATION_WIDTH",
    "SETTINGS_PAGE_BOTTOM_MARGIN",
    "SETTINGS_PAGE_HEADER_TO_FIRST_GROUP_SPACING",
    "SETTINGS_PAGE_HORIZONTAL_MARGIN",
    "SETTINGS_PAGE_TOP_MARGIN",
    "qcolor_from_rgba",
    "settings_accent_color",
    "settings_card_border_color",
    "settings_card_fill_color",
    "settings_card_overlay_color",
    "settings_disabled_foreground_color",
    "settings_navigation_overlay_color",
    "settings_navigation_selected_fill_color",
]
