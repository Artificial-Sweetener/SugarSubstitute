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

"""Define dimension-row action contracts and immutable preset values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtWidgets import QWidget

from substitute.application.node_behavior import DimensionFieldPair


class DimensionSide(Enum):
    """Identify which dimension field anchors a row action."""

    WIDTH = "width"
    HEIGHT = "height"


class DimensionContextMenuContent(Enum):
    """Select the dimension actions exposed by one presentation surface."""

    FULL = "full"
    SAVE_ONLY = "save_only"


@dataclass(frozen=True)
class AspectRatioPreset:
    """Describe one width-to-height aspect-ratio menu option."""

    label: str
    width_units: int
    height_units: int


@dataclass(frozen=True)
class DimensionRowBinding:
    """Store widgets and columns for one actionable dimension row."""

    pair: DimensionFieldPair
    width_widget: QWidget
    height_widget: QWidget
    width_column: QWidget
    height_column: QWidget


LANDSCAPE_ASPECT_RATIOS = (
    AspectRatioPreset("1:1", 1, 1),
    AspectRatioPreset("5:4", 5, 4),
    AspectRatioPreset("4:3", 4, 3),
    AspectRatioPreset("3:2", 3, 2),
    AspectRatioPreset("16:9", 16, 9),
    AspectRatioPreset("2:1", 2, 1),
    AspectRatioPreset("21:9", 21, 9),
)

PORTRAIT_ASPECT_RATIOS = (
    AspectRatioPreset("1:1", 1, 1),
    AspectRatioPreset("4:5", 4, 5),
    AspectRatioPreset("3:4", 3, 4),
    AspectRatioPreset("2:3", 2, 3),
    AspectRatioPreset("9:16", 9, 16),
    AspectRatioPreset("1:2", 1, 2),
    AspectRatioPreset("9:21", 9, 21),
)


__all__ = [
    "AspectRatioPreset",
    "DimensionContextMenuContent",
    "DimensionRowBinding",
    "DimensionSide",
    "LANDSCAPE_ASPECT_RATIOS",
    "PORTRAIT_ASPECT_RATIOS",
]
