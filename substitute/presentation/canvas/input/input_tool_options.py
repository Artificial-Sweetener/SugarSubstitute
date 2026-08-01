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

"""Render contextual built-in Input tool options over authoritative document state."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPixmap, QShowEvent
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QWidget
from cutecanvas import BrushPreset
from qfluentwidgets import CaptionLabel, Slider  # type: ignore[import-untyped]
from sugarsubstitute_shared.presentation.localization import app_text
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    BRUSH_OPTIONS_ID,
)
from substitute.presentation.canvas.tools import CanvasToolRuntime


class OptionsSignalPort(Protocol):
    """Describe Qt-compatible signal subscription used by options widgets."""

    def connect(self, callback: object) -> object:
        """Connect one callback."""


class InputToolOptionsDocumentPort(Protocol):
    """Describe brush state consumed by contextual controls."""

    brushPresetChanged: OptionsSignalPort
    maskContentChanged: OptionsSignalPort
    toolContextChanged: OptionsSignalPort

    def brush_preset(self) -> BrushPreset:
        """Return the active immutable brush definition."""

    def set_brush_preset(self, preset: BrushPreset) -> bool:
        """Replace the active immutable brush definition."""

    def render_brush_tip_preview(
        self,
        logical_size: QSize,
        *,
        device_pixel_ratio: float,
        color: QColor,
    ) -> QImage:
        """Render a DPR-aware brush-tip image."""


_BRUSH_PREVIEW_SIZE = QSize(48, 48)


class InputBrushOptions(QWidget):
    """Edit brush size, hardness, and opacity with a live authoritative preview."""

    def __init__(
        self,
        document: InputToolOptionsDocumentPort,
        parent: QWidget,
    ) -> None:
        """Build compact Fluent controls and bind brush state changes."""

        super().__init__(parent)
        self.setObjectName("InputBrushOptions")
        self._document = document
        self._synchronizing = False
        self.preview = QLabel(self)
        self.preview.setObjectName("InputBrushTipPreview")
        self.preview.setFixedSize(_BRUSH_PREVIEW_SIZE)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.size_slider, self.size_value = self._slider_row(
            minimum=1,
            maximum=1000,
        )
        self.hardness_slider, self.hardness_value = self._slider_row(
            minimum=0,
            maximum=100,
        )
        self.opacity_slider, self.opacity_value = self._slider_row(
            minimum=0,
            maximum=100,
        )
        controls = QGridLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(4)
        self._add_row(
            controls,
            0,
            app_text("Size"),
            self.size_slider,
            self.size_value,
        )
        self._add_row(
            controls,
            1,
            app_text("Hardness"),
            self.hardness_slider,
            self.hardness_value,
        )
        self._add_row(
            controls,
            2,
            app_text("Opacity"),
            self.opacity_slider,
            self.opacity_value,
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.preview)
        layout.addLayout(controls)
        self.size_slider.valueChanged.connect(self._apply_values)
        self.hardness_slider.valueChanged.connect(self._apply_values)
        self.opacity_slider.valueChanged.connect(self._apply_values)
        document.brushPresetChanged.connect(self.synchronize)
        self.synchronize()

    def synchronize(self, *_args: object) -> None:
        """Project the authoritative preset without feeding controls back."""

        preset = self._document.brush_preset()
        self._synchronizing = True
        try:
            self.size_slider.setValue(round(preset.size))
            self.hardness_slider.setValue(round(preset.hardness * 100.0))
            self.opacity_slider.setValue(round(preset.opacity * 100.0))
            self.size_value.setText(app_text("%1 px", f"{preset.size:.0f}"))
            self.hardness_value.setText(f"{preset.hardness * 100.0:.0f}%")
            self.opacity_value.setText(f"{preset.opacity * 100.0:.0f}%")
        finally:
            self._synchronizing = False
        self._refresh_preview()

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh physical-density-dependent preview when shown."""

        super().showEvent(event)
        self._refresh_preview()

    def _apply_values(self, _value: int) -> None:
        """Replace the complete brush preset from current control values."""

        if self._synchronizing:
            return
        preset = self._document.brush_preset()
        self._document.set_brush_preset(
            replace(
                preset,
                size=float(self.size_slider.value()),
                hardness=self.hardness_slider.value() / 100.0,
                opacity=self.opacity_slider.value() / 100.0,
            )
        )

    def _refresh_preview(self) -> None:
        """Render the active brush at this surface's actual DPR."""

        image = self._document.render_brush_tip_preview(
            _BRUSH_PREVIEW_SIZE,
            device_pixel_ratio=max(1.0, self.devicePixelRatioF()),
            color=QColor(255, 255, 255),
        )
        self.preview.setPixmap(QPixmap.fromImage(image))

    def _slider_row(
        self,
        *,
        minimum: int,
        maximum: int,
    ) -> tuple[Slider, CaptionLabel]:
        """Create one Fluent slider and fixed-width value label."""

        slider = Slider(Qt.Orientation.Horizontal, self)
        slider.setRange(minimum, maximum)
        slider.setFixedWidth(128)
        value = CaptionLabel("", self)
        value.setMinimumWidth(48)
        return slider, value

    @staticmethod
    def _add_row(
        layout: QGridLayout,
        row: int,
        text: str,
        slider: Slider,
        value: CaptionLabel,
    ) -> None:
        """Add one localized control row."""

        layout.addWidget(CaptionLabel(text), row, 0)
        layout.addWidget(slider, row, 1)
        layout.addWidget(value, row, 2)


def install_input_tool_options(
    runtime: CanvasToolRuntime,
    document: InputToolOptionsDocumentPort,
) -> None:
    """Register built-in Input option surfaces through the runtime boundary."""

    runtime.register_options(
        BRUSH_OPTIONS_ID,
        lambda parent: InputBrushOptions(document, parent),
    )


__all__ = [
    "InputBrushOptions",
    "install_input_tool_options",
]
