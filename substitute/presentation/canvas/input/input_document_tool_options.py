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

"""Adapt CuteCanvas brush and mask state to contextual Input tool options."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from cutecanvas import BrushPreset, CuteCanvas


class ToolOptionsSignalPort(Protocol):
    """Describe one host signal exposed to contextual tool controls."""

    def connect(self, callback: object) -> object:
        """Connect one options-state listener."""


class InputDocumentToolOptions:
    """Own the Input toolbar's focused CuteCanvas option operations."""

    def __init__(
        self,
        *,
        canvas: CuteCanvas,
        brush_preset_changed: ToolOptionsSignalPort,
        mask_content_changed: ToolOptionsSignalPort,
        tool_context_changed: ToolOptionsSignalPort,
    ) -> None:
        """Bind the editor surface and host-owned context signals."""
        self._canvas = canvas
        self.brushPresetChanged = brush_preset_changed
        self.maskContentChanged = mask_content_changed
        self.toolContextChanged = tool_context_changed

    def active_mask_id(self) -> UUID | None:
        """Return the authoritative active mask identity."""
        return self._canvas.activeMaskID()

    def brush_preset(self) -> BrushPreset:
        """Return the active immutable CuteCanvas brush definition."""
        return self._canvas.brushPreset()

    def set_brush_preset(self, preset: BrushPreset) -> bool:
        """Replace the complete active CuteCanvas brush definition."""
        return bool(self._canvas.setBrushPreset(preset))

    def render_brush_tip_preview(
        self,
        logical_size: QSize,
        *,
        device_pixel_ratio: float,
        color: QColor,
    ) -> QImage:
        """Render a compact DPR-aware preview from the active brush definition."""
        return self._canvas.renderBrushTipPreview(
            logical_size,
            device_pixel_ratio=device_pixel_ratio,
            color=color,
        )


__all__ = ["InputDocumentToolOptions"]
