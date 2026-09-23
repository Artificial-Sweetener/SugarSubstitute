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

"""Cache complete LoRA chip rasters by their visual identity."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)

_MAX_ENTRIES = 128
type LoraPaintCacheKey = tuple[object, ...]
type LoraRasterPainter = Callable[[QPainter, QRectF], None]


class PromptLoraPaintCache:
    """Own bounded device-pixel-aware LoRA chip raster reuse."""

    def __init__(self) -> None:
        """Create an empty least-recently-used raster cache."""

        self._pixmaps: OrderedDict[LoraPaintCacheKey, QPixmap] = OrderedDict()

    def paint(
        self,
        painter: QPainter,
        rect: QRectF,
        *,
        key: LoraPaintCacheKey,
        render: LoraRasterPainter,
    ) -> None:
        """Draw a cached chip or render and retain one local-coordinate raster."""

        cached = self._pixmaps.get(key)
        if cached is not None:
            self._pixmaps.move_to_end(key)
            painter.drawPixmap(rect.topLeft(), cached)
            return
        device_pixel_ratio = painter_device_pixel_ratio(painter)
        pixel_size = QSize(
            max(1, round(rect.width() * device_pixel_ratio)),
            max(1, round(rect.height() * device_pixel_ratio)),
        )
        pixmap = QPixmap(pixel_size)
        pixmap.setDevicePixelRatio(device_pixel_ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        cache_painter = QPainter(pixmap)
        try:
            render(
                cache_painter,
                QRectF(0.0, 0.0, rect.width(), rect.height()),
            )
        finally:
            cache_painter.end()
        self._pixmaps[key] = pixmap
        self._pixmaps.move_to_end(key)
        while len(self._pixmaps) > _MAX_ENTRIES:
            self._pixmaps.popitem(last=False)
        painter.drawPixmap(rect.topLeft(), pixmap)


def lora_paint_cache_key(
    painter: QPainter,
    rect: QRectF,
    run: PromptProjectionRun,
    token: PromptProjectionToken,
    *,
    base_font: QFont,
    fill: QColor,
    border: QColor,
    accent: QColor,
    text_color: QColor,
    selected: bool,
    banner: QPixmap | None,
) -> LoraPaintCacheKey:
    """Return the complete visual identity for one cached LoRA chip."""

    return (
        round(rect.width(), 3),
        round(rect.height(), 3),
        round(painter_device_pixel_ratio(painter), 3),
        base_font.toString(),
        int(fill.rgba()),
        int(border.rgba()),
        int(accent.rgba()),
        int(text_color.rgba()),
        run.display_text,
        token.value_text,
        token.lora_version_text,
        token.lora_status,
        token.exists,
        token.active,
        token.editing_value_text,
        token.editing_slot_width,
        selected,
        0 if banner is None else int(banner.cacheKey()),
    )


def painter_device_pixel_ratio(painter: QPainter) -> float:
    """Return a positive device-pixel ratio for the active paint target."""

    device = painter.device()
    ratio = 1.0 if device is None else float(device.devicePixelRatioF())
    return max(1.0, ratio)


__all__ = [
    "PromptLoraPaintCache",
    "lora_paint_cache_key",
    "painter_device_pixel_ratio",
]
