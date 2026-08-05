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

"""Install the brush-owned Input settings surface into the tool runtime."""

from __future__ import annotations

from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QWidget

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    BRUSH_OPTIONS_ID,
)
from substitute.presentation.canvas.tools import CanvasToolRuntime

from .input_brush_settings import InputBrushSettingsSection
from .input_expandable_settings import InputExpandableSettingsControl
from .input_tool_options_contracts import InputToolOptionsDocumentPort


class InputBrushSettingsControl(InputExpandableSettingsControl):
    """Present brush settings through the shared expandable settings chrome."""

    def __init__(
        self,
        document: InputToolOptionsDocumentPort,
        parent: QWidget,
    ) -> None:
        """Create the independently mounted brush settings control."""
        self.brush_settings = InputBrushSettingsSection(document, parent)
        super().__init__(self.brush_settings, parent)
        self.setObjectName("InputBrushSettingsControl")

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh physical-density-dependent brush preview when shown."""
        super().showEvent(event)
        self.brush_settings.refresh_preview()


def install_input_tool_options(
    runtime: CanvasToolRuntime,
    document: InputToolOptionsDocumentPort,
) -> None:
    """Register the Brush tool's independently owned options surface."""
    runtime.register_options(
        BRUSH_OPTIONS_ID,
        lambda parent: InputBrushSettingsControl(document, parent),
    )


__all__ = ["InputBrushSettingsControl", "install_input_tool_options"]
