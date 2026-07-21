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

"""Own reorder chrome painted below projection text on the editor surface."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPainter

from .chip_painter import PromptProjectionChipPainter
from .reorder_chip_geometry import PromptReorderChipGeometry


@dataclass(frozen=True, slots=True)
class PromptReorderSurfaceChromeStyle:
    """Describe one immutable projection-surface chip style."""

    fill_color: QColor
    border_color: QColor
    outline_only: bool = False
    outline_width: float = 1.0
    opacity: float = 1.0


@dataclass(frozen=True, slots=True)
class PromptReorderSurfaceChromeChip:
    """Bind one semantic chip to chrome drawn below its projection text."""

    segment_index: int
    geometry: PromptReorderChipGeometry
    style: PromptReorderSurfaceChromeStyle


@dataclass(frozen=True, slots=True)
class PromptReorderSurfaceChromeSnapshot:
    """Carry chrome with the exact projection identity that owns its geometry."""

    source_revision: int
    viewport_rect: QRect
    scroll_offset: int
    preview_generation: int | None
    mode: str
    chips: tuple[PromptReorderSurfaceChromeChip, ...]

    def matches(
        self,
        *,
        source_revision: int,
        viewport_rect: QRect,
        scroll_offset: int,
        preview_generation: int | None,
        mode: str,
    ) -> bool:
        """Return whether this chrome belongs to the active projection paint."""

        return (
            self.source_revision == source_revision
            and self.viewport_rect == viewport_rect
            and self.scroll_offset == scroll_offset
            and self.preview_generation == preview_generation
            and self.mode == mode
        )


class PromptReorderSurfaceChromePainter:
    """Paint stationary reorder chrome before the projection paints its text."""

    def __init__(self) -> None:
        """Initialize the shared projection geometry painter."""

        self._chip_painter = PromptProjectionChipPainter()

    def paint(
        self,
        painter: QPainter,
        snapshot: PromptReorderSurfaceChromeSnapshot,
    ) -> None:
        """Paint every prepared stationary chip in semantic order."""

        for chip in snapshot.chips:
            self._chip_painter.paint_chip_geometry(
                painter=painter,
                geometry=chip.geometry,
                style=chip.style,
            )


__all__ = [
    "PromptReorderSurfaceChromeChip",
    "PromptReorderSurfaceChromePainter",
    "PromptReorderSurfaceChromeSnapshot",
    "PromptReorderSurfaceChromeStyle",
]
