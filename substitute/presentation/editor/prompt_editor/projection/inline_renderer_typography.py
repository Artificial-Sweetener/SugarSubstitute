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

"""Provide typography shared by prompt inline object renderers."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontMetricsF


def inline_weight_font(base_font: QFont) -> QFont:
    """Return the compact font shared by inline numeric weight labels."""

    weight_font = QFont(base_font)
    if base_font.pointSizeF() > 0:
        weight_font.setPointSizeF(max(5.4, base_font.pointSizeF() - 4.0))
    elif base_font.pixelSize() > 0:
        weight_font.setPixelSize(max(6, base_font.pixelSize() - 4))
    weight_font.setWeight(QFont.Weight.DemiBold)
    return weight_font


def centered_text_baseline(rect: QRectF, metrics: QFontMetricsF) -> float:
    """Return the baseline that vertically centers text inside one rect."""

    return rect.center().y() + ((metrics.ascent() - metrics.descent()) / 2.0)
