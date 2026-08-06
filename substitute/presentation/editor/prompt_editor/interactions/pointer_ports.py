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

"""Own optional pointer collaborators used by the prompt projection surface."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF

from substitute.presentation.editor.prompt_editor.projection.prepared_frame import (
    PromptProjectionPreparedFrame,
)

PromptPointHandler = Callable[[QPointF], bool]
PromptRegionPointHandler = Callable[[QPointF, PromptProjectionPreparedFrame], bool]
PromptRegionHoverHandler = Callable[
    [QPointF | None, PromptProjectionPreparedFrame], None
]


class PromptSurfacePointerInteractions:
    """Route optional pointer intent without giving the surface feature policy."""

    def __init__(self) -> None:
        """Initialize every optional collaborator as absent."""

        self._weight_click: PromptPointHandler | None = None
        self._weight_double_click: PromptPointHandler | None = None
        self._region_double_click: PromptRegionPointHandler | None = None
        self._region_hover: PromptRegionHoverHandler | None = None
        self._region_keyboard_rename: Callable[[], bool] | None = None

    def set_weight_click_handler(self, handler: PromptPointHandler | None) -> None:
        """Install the exact-weight click collaborator."""

        self._weight_click = handler

    def set_weight_double_click_handler(
        self, handler: PromptPointHandler | None
    ) -> None:
        """Install the exact-weight double-click collaborator."""

        self._weight_double_click = handler

    def set_region_double_click_handler(
        self, handler: PromptRegionPointHandler | None
    ) -> None:
        """Install the regional separator double-click collaborator."""

        self._region_double_click = handler

    def set_region_hover_handler(
        self, handler: PromptRegionHoverHandler | None
    ) -> None:
        """Install the transient regional hover collaborator."""

        self._region_hover = handler

    def set_region_keyboard_rename_handler(
        self, handler: Callable[[], bool] | None
    ) -> None:
        """Install the caret-based regional rename collaborator."""

        self._region_keyboard_rename = handler

    def handle_weight_click(self, position: QPointF) -> bool:
        """Offer one click to exact-weight editing."""

        return self._weight_click is not None and self._weight_click(position)

    def handle_weight_double_click(self, position: QPointF) -> bool:
        """Offer one double click to exact-weight editing."""

        return self._weight_double_click is not None and self._weight_double_click(
            position
        )

    def handle_region_double_click(
        self,
        position: QPointF,
        frame: PromptProjectionPreparedFrame,
    ) -> bool:
        """Offer one double click to regional separator interaction."""

        return self._region_double_click is not None and self._region_double_click(
            position, frame
        )

    def publish_region_hover(
        self,
        position: QPointF | None,
        frame: PromptProjectionPreparedFrame,
    ) -> None:
        """Publish or clear one regional separator hover position."""

        if self._region_hover is not None:
            self._region_hover(position, frame)

    def handle_region_keyboard_rename(self) -> bool:
        """Offer an F2 rename gesture to regional separator interaction."""

        return (
            self._region_keyboard_rename is not None and self._region_keyboard_rename()
        )


__all__ = ["PromptSurfacePointerInteractions"]
