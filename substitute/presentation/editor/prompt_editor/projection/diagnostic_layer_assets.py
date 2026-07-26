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

"""Attach cached wave rasters to prepared diagnostic command layers."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtGui import QColor

from .diagnostic_render_layer import (
    EMPTY_DIAGNOSTIC_RENDER_LAYER,
    PromptDiagnosticRenderLayer,
)
from .diagnostic_wave_tiles import PromptDiagnosticWaveTileCache

_DIAGNOSTIC_WAVE_PEN_WIDTH = 1.2
_DIAGNOSTIC_WAVE_RADIUS = 2.0


class PromptDiagnosticLayerAssetPreparer:
    """Own bounded wave-raster selection for diagnostic layer snapshots."""

    def __init__(self) -> None:
        """Create the bounded raster cache used only during publication."""

        self._wave_tiles = PromptDiagnosticWaveTileCache()

    def prepare(
        self,
        layer: PromptDiagnosticRenderLayer,
        *,
        device_pixel_ratio: float,
    ) -> PromptDiagnosticRenderLayer:
        """Attach the exact wave tile selected before paint."""

        if not layer.underlines:
            return EMPTY_DIAGNOSTIC_RENDER_LAYER
        normalized_ratio = max(1.0, device_pixel_ratio)
        tile = self._wave_tiles.tile(
            color=QColor.fromRgba(layer.color_rgba),
            radius=_DIAGNOSTIC_WAVE_RADIUS,
            pen_width=_DIAGNOSTIC_WAVE_PEN_WIDTH,
            device_pixel_ratio=normalized_ratio,
        )
        return replace(
            layer,
            wave_tile=tile,
            wave_height=tile.height() / normalized_ratio,
        )


__all__ = ["PromptDiagnosticLayerAssetPreparer"]
