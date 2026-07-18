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

"""Own editor content gutters across cube-stack presentation modes."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.panel.widgets.masonry_grid_layout import (
    EDITOR_SECTION_GAP,
)

CUBE_STACK_ADJACENT_GUTTER = 6
CANVAS_ADJACENT_GUTTER = 14
DIRECT_WORKFLOW_LEFT_GUTTER = EDITOR_SECTION_GAP


@dataclass(slots=True)
class EditorPanelContentGutterController:
    """Apply fixed-edge editor gutters across document presentation modes."""

    content: QWidget

    def __post_init__(self) -> None:
        """Initialize content at the normal cube-stack-adjacent endpoint."""

        self.apply_cube_stack_unavailable_progress(0.0)

    def apply_cube_stack_unavailable_progress(self, progress: float) -> None:
        """Interpolate the fixed left gutter toward direct-workflow spacing."""

        clamped = max(0.0, min(1.0, float(progress)))
        left_gutter = round(
            CUBE_STACK_ADJACENT_GUTTER
            + ((DIRECT_WORKFLOW_LEFT_GUTTER - CUBE_STACK_ADJACENT_GUTTER) * clamped)
        )
        margins = self.content.contentsMargins()
        self.content.setContentsMargins(
            left_gutter,
            margins.top(),
            CANVAS_ADJACENT_GUTTER,
            margins.bottom(),
        )

    def horizontal_gutters(self) -> tuple[int, int]:
        """Return the live left and right content gutters."""

        margins = self.content.contentsMargins()
        return margins.left(), margins.right()


__all__ = [
    "CANVAS_ADJACENT_GUTTER",
    "CUBE_STACK_ADJACENT_GUTTER",
    "DIRECT_WORKFLOW_LEFT_GUTTER",
    "EditorPanelContentGutterController",
]
