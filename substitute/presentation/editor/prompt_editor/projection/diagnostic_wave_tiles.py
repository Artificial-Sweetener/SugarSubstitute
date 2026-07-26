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

"""Build and retain bounded diagnostic underline wave tiles."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import math
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

_GOLDEN_RATIO = 1.61803399
_MIN_RADIUS = 1.0
_TILE_TARGET_WIDTH = 100.0
_WAVE_TILE_CACHE_LIMIT: Final[int] = 16


@dataclass(frozen=True, slots=True)
class PromptDiagnosticWaveStyle:
    """Identify one reusable diagnostic wave raster style."""

    color_rgba: int
    radius: float
    pen_width: float
    device_pixel_ratio: float


class PromptDiagnosticWaveTileCache:
    """Own bounded least-recently-used diagnostic wave pixmaps."""

    def __init__(self, *, capacity: int = _WAVE_TILE_CACHE_LIMIT) -> None:
        """Create a cache with a positive hard raster budget."""

        if capacity <= 0:
            raise ValueError("diagnostic wave cache capacity must be positive")
        self._capacity = capacity
        self._tiles: OrderedDict[PromptDiagnosticWaveStyle, QPixmap] = OrderedDict()

    @property
    def entry_count(self) -> int:
        """Return the number of retained raster styles."""

        return len(self._tiles)

    def tile(
        self,
        *,
        color: QColor,
        radius: float,
        pen_width: float,
        device_pixel_ratio: float,
    ) -> QPixmap:
        """Return one cached tile, building only on an exact style miss."""

        normalized_radius = max(_MIN_RADIUS, radius)
        normalized_ratio = max(1.0, device_pixel_ratio)
        style = PromptDiagnosticWaveStyle(
            color_rgba=int(color.rgba()),
            radius=round(normalized_radius, 2),
            pen_width=round(pen_width, 2),
            device_pixel_ratio=round(normalized_ratio, 2),
        )
        cached = self._tiles.get(style)
        if cached is not None:
            self._tiles.move_to_end(style)
            return cached
        tile = _build_wave_tile(style)
        self._tiles[style] = tile
        while len(self._tiles) > self._capacity:
            self._tiles.popitem(last=False)
        return tile


def _build_wave_tile(style: PromptDiagnosticWaveStyle) -> QPixmap:
    """Rasterize one diagnostic wave style."""

    half_period = max(2.0, style.radius * _GOLDEN_RATIO)
    logical_width = math.ceil(_TILE_TARGET_WIDTH / (2.0 * half_period)) * (
        2.0 * half_period
    )
    logical_height = max(1.0, style.radius * 2.0 + style.pen_width)
    pixmap = QPixmap(
        max(1, math.ceil(logical_width * style.device_pixel_ratio)),
        max(1, math.ceil(logical_height * style.device_pixel_ratio)),
    )
    pixmap.setDevicePixelRatio(style.device_pixel_ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    path = _wave_path(
        width=logical_width,
        center_y=logical_height / 2.0,
        radius=style.radius,
        half_period=half_period,
    )
    pen = QPen(QColor.fromRgba(style.color_rgba), style.pen_width)
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
    finally:
        painter.end()
    return pixmap


def _wave_path(
    *,
    width: float,
    center_y: float,
    radius: float,
    half_period: float,
) -> QPainterPath:
    """Build a smooth repeated diagnostic wave path."""

    path = QPainterPath()
    path.moveTo(0.0, center_y)
    x = 0.0
    direction = 1.0
    while x < width:
        next_x = min(width, x + half_period)
        path.quadTo(
            x + (next_x - x) / 2.0,
            center_y + radius * direction,
            next_x,
            center_y,
        )
        x = next_x
        direction *= -1.0
    return path


__all__ = [
    "PromptDiagnosticWaveStyle",
    "PromptDiagnosticWaveTileCache",
]
