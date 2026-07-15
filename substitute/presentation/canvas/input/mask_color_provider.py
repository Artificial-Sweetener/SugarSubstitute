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

"""Adapt domain mask color policy to Qt colors."""

from __future__ import annotations

from typing import cast

from PySide6.QtGui import QColor
from qfluentwidgets.common.style_sheet import themeColor  # type: ignore[import-untyped]

from substitute.domain.canvas.mask_color_scheme import mask_color_hue


def input_mask_color(index: int, total_masks: int) -> QColor:
    """Return the themed Qt color for one mask in a related mask set."""

    base_color = QColor(themeColor())
    hue, saturation, value, _alpha = cast(
        tuple[int, int, int, int], base_color.getHsv()
    )
    saturation = max(saturation, 200)
    value = max(value, 220)

    if index <= 0:
        return base_color

    return QColor.fromHsv(
        mask_color_hue(hue, index, total_masks),
        saturation,
        value,
    )
