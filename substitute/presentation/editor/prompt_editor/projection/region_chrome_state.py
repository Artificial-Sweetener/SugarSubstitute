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

"""Define immutable regional chrome commands consumed by prompt rendering."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QLineF, QPointF
from PySide6.QtGui import QColor, QFont, QPen

from substitute.domain.appearance import RgbColor


@dataclass(frozen=True, slots=True)
class PromptRegionChromeStroke:
    """Bind same-colored regional geometry for one paint operation."""

    region_index: int
    lines: tuple[QLineF, ...]
    pen: QPen


@dataclass(frozen=True, slots=True)
class PromptRegionChromeLabel:
    """Describe one centered authored separator name."""

    text: str
    baseline: QPointF
    color: QColor
    font: QFont


@dataclass(frozen=True, slots=True)
class PromptRegionChromeSnapshot:
    """Store paint-ready separator and regional rail geometry."""

    layout_snapshot_identity: int
    accent: RgbColor
    divider_lines: tuple[QLineF, ...]
    rail_lines: tuple[QLineF, ...]
    paint_lines: tuple[QLineF, ...]
    pen: QPen
    strokes: tuple[PromptRegionChromeStroke, ...]
    labels: tuple[PromptRegionChromeLabel, ...]
    visited_line_count: int


__all__ = [
    "PromptRegionChromeLabel",
    "PromptRegionChromeSnapshot",
    "PromptRegionChromeStroke",
]
