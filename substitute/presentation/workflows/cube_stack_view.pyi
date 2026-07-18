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

from __future__ import annotations

from typing import Any

CubeCloseButtonDisplayMode: Any
CUBE_STACK_EXPANDED_WIDTH: int
CUBE_STACK_COMPACT_WIDTH: int
CUBE_STACK_EDGE_INSET: int
CUBE_ITEM_EXPANDED_WIDTH: int
CUBE_ITEM_COMPACT_WIDTH: int
CUBE_ITEM_HEIGHT: int
CUBE_ITEM_ICON_INSET_EXPANDED: int
CUBE_ITEM_ICON_SIZE_EXPANDED: int
CUBE_ITEM_ICON_SIZE_COMPACT: int
CUBE_ITEM_ICON_X: int
CUBE_ITEM_TEXT_PRIMARY_HEIGHT: int
CUBE_ITEM_TEXT_SECONDARY_HEIGHT: int
CUBE_ITEM_TEXT_ROW_OVERLAP: int
CUBE_ITEM_TEXT_BLOCK_HEIGHT: int
CUBE_ITEM_TEXT_GAP_EXPANDED: int
CUBE_ITEM_CLOSE_TEXT_RESERVE: int
CUBE_ITEM_CLOSE_BUTTON_SIZE: int

class CubeStack:
    cubeChanged: Any
    cubeMoved: Any
    cubeRenameEditRequested: Any
    cubeRenameRequested: Any
    cubeBypassToggleRequested: Any
    aliasEditingFinished: Any
    cubeCloseRequested: Any
    cubeStackWheelRerouteRequested: Any
    tabMouseReleased: Any

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def select_cube(self, route_key: str, *, animated: bool = ...) -> None: ...
    def reorder_by_route_keys(self, route_keys: list[str]) -> None: ...
    def realign_indicator(self, *, animated: bool = ...) -> None: ...
    def begin_alias_editing(self, route_key: str) -> bool: ...
    def setCompact(self, compact: bool) -> None: ...
    def isCompact(self) -> bool: ...
    def beginCompactTransition(self, target_compact: bool) -> None: ...
    def applyCompactTransition(
        self,
        *,
        stack_width: int,
        item_width: int,
        compact_progress: float,
    ) -> None: ...
    def finishCompactTransition(self, target_compact: bool) -> None: ...
    def setTabPresentation(self, index: int, **kwargs: Any) -> None: ...
    def setTabBypassed(self, index: int, bypassed: bool) -> None: ...
