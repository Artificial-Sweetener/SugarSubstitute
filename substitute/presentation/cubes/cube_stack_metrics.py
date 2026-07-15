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

"""Define shared cube-stack card presentation metrics."""

from __future__ import annotations

from substitute.presentation.shell.chrome_style import CUBE_STACK_TOP_INSET

CUBE_ITEM_EXPANDED_WIDTH = 212
CUBE_ITEM_ICON_INSET_EXPANDED = 6
CUBE_ITEM_TEXT_PRIMARY_HEIGHT = 20
CUBE_ITEM_TEXT_SECONDARY_HEIGHT = 18
CUBE_ITEM_TEXT_ROW_OVERLAP = 4
CUBE_ITEM_TEXT_BLOCK_HEIGHT = (
    CUBE_ITEM_TEXT_PRIMARY_HEIGHT
    + CUBE_ITEM_TEXT_SECONDARY_HEIGHT
    - CUBE_ITEM_TEXT_ROW_OVERLAP
)
CUBE_ITEM_ICON_SIZE_EXPANDED = CUBE_ITEM_TEXT_BLOCK_HEIGHT
CUBE_ITEM_HEIGHT = CUBE_ITEM_ICON_SIZE_EXPANDED + (CUBE_ITEM_ICON_INSET_EXPANDED * 2)
CUBE_ITEM_COMPACT_WIDTH = CUBE_ITEM_HEIGHT
CUBE_ITEM_ICON_SIZE_COMPACT = CUBE_ITEM_ICON_SIZE_EXPANDED
CUBE_ITEM_ICON_X = CUBE_ITEM_ICON_INSET_EXPANDED
CUBE_ITEM_TEXT_GAP_EXPANDED = 6
CUBE_ITEM_CLOSE_TEXT_RESERVE = 30
CUBE_ITEM_CLOSE_BUTTON_SIZE = 18
CUBE_STACK_EDGE_INSET = CUBE_STACK_TOP_INSET
CUBE_STACK_EXPANDED_WIDTH = CUBE_ITEM_EXPANDED_WIDTH + (CUBE_STACK_EDGE_INSET * 2)
CUBE_STACK_COMPACT_WIDTH = CUBE_ITEM_COMPACT_WIDTH + (CUBE_STACK_EDGE_INSET * 2)
CUBE_STACK_ITEM_SPACING = 4

__all__ = [
    "CUBE_ITEM_CLOSE_BUTTON_SIZE",
    "CUBE_ITEM_CLOSE_TEXT_RESERVE",
    "CUBE_ITEM_COMPACT_WIDTH",
    "CUBE_ITEM_EXPANDED_WIDTH",
    "CUBE_ITEM_HEIGHT",
    "CUBE_ITEM_ICON_INSET_EXPANDED",
    "CUBE_ITEM_ICON_SIZE_COMPACT",
    "CUBE_ITEM_ICON_SIZE_EXPANDED",
    "CUBE_ITEM_ICON_X",
    "CUBE_ITEM_TEXT_BLOCK_HEIGHT",
    "CUBE_ITEM_TEXT_GAP_EXPANDED",
    "CUBE_ITEM_TEXT_PRIMARY_HEIGHT",
    "CUBE_ITEM_TEXT_ROW_OVERLAP",
    "CUBE_ITEM_TEXT_SECONDARY_HEIGHT",
    "CUBE_STACK_COMPACT_WIDTH",
    "CUBE_STACK_EDGE_INSET",
    "CUBE_STACK_EXPANDED_WIDTH",
    "CUBE_STACK_ITEM_SPACING",
]
