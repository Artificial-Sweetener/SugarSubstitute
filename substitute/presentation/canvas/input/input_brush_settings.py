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

"""Present brush-specific Input options from authoritative document state."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import QGridLayout, QWidget
from cutecanvas import CuteCanvas
from qfluentwidgets import CaptionLabel, SegmentedItem, Slider  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    apply_application_text,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_GAP,
)
from substitute.presentation.localization import LocalizedCaptionLabel

from .input_tool_options_contracts import InputToolOptionsDocumentPort

_BRUSH_PREVIEW_SIZE = QSize(20, 20)


class InputBrushSettingsSection(QObject):
    """Own brush header presentation and detailed brush value controls."""

    def __init__(
        self,
        document: InputToolOptionsDocumentPort,
        owner: QWidget,
    ) -> None:
        """Build one brush header and its independently owned details body."""

        super().__init__(owner)
        self._document = document
        self._synchronizing = False
        self._preview_image = QImage()

        self.header_button = SegmentedItem("", owner)
        self.header_button.setObjectName("InputBrushSettingsHeader")
        self.header_button.setIconSize(_BRUSH_PREVIEW_SIZE)
        apply_application_text(self.header_button, app_text("Brush settings"))

        self.details = QWidget(owner)
        self.details.setObjectName("InputBrushSettingsDetails")
        self.size_slider, self.size_value = self._slider_row(minimum=1, maximum=1000)
        self.hardness_slider, self.hardness_value = self._slider_row(
            minimum=0,
            maximum=100,
        )
        self.opacity_slider, self.opacity_value = self._slider_row(
            minimum=0,
            maximum=100,
        )
        controls = QGridLayout(self.details)
        controls.setContentsMargins(
            CANVAS_CHROME_GAP,
            CANVAS_CHROME_GAP,
            CANVAS_CHROME_GAP,
            CANVAS_CHROME_GAP,
        )
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(4)
        self._add_row(controls, 0, app_text("Size"), self.size_slider, self.size_value)
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
        self.details.hide()

        self.size_slider.valueChanged.connect(self._apply_values)
        self.hardness_slider.valueChanged.connect(self._apply_values)
        self.opacity_slider.valueChanged.connect(self._apply_values)
        document.brushPresetChanged.connect(self.synchronize)
        document.toolContextChanged.connect(self.synchronize)
        document.canvasOperationChanged.connect(self.synchronize)
        self.synchronize()

    def synchronize(self, *_args: object) -> None:
        """Project the authoritative preset without feeding controls back."""

        preset = self._document.brush_preset()
        self._synchronizing = True
        try:
            self.size_slider.setValue(round(preset.size))
            self.hardness_slider.setValue(round(preset.hardness * 100.0))
            self.opacity_slider.setValue(round(preset.opacity * 100.0))
            apply_application_text(
                self.size_value,
                app_text("%1 px", f"{preset.size:.0f}"),
            )
            self.hardness_value.setText(f"{preset.hardness * 100.0:.0f}%")
            self.opacity_value.setText(f"{preset.opacity * 100.0:.0f}%")
        finally:
            self._synchronizing = False
        self.refresh_preview()

    def set_details_visible(self, visible: bool) -> None:
        """Show or hide the brush-owned detailed controls."""

        self.details.setVisible(visible)

    def preview_image(self) -> QImage:
        """Return the detached rendered preview used by the compact header."""

        return QImage(self._preview_image)

    def refresh_preview(self) -> None:
        """Render the active brush at the owning surface's actual DPR."""

        image = self._document.render_brush_tip_preview(
            _BRUSH_PREVIEW_SIZE,
            device_pixel_ratio=max(1.0, self.header_button.devicePixelRatioF()),
            color=self._preview_color(),
        )
        self._preview_image = QImage(image)
        self.header_button.setIcon(QIcon(QPixmap.fromImage(image)))

    def _preview_color(self) -> QColor:
        """Represent transparent erasure with a visible neutral white tip."""

        if self._document.current_canvas_operation() == CuteCanvas.CONTROL_MODE_ERASER:
            return QColor(Qt.GlobalColor.white)
        return self._document.brush_preview_color()

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

    def _slider_row(
        self,
        *,
        minimum: int,
        maximum: int,
    ) -> tuple[Slider, CaptionLabel]:
        """Create one Fluent slider and fixed-width value label."""

        slider = Slider(Qt.Orientation.Horizontal, self.details)
        slider.setRange(minimum, maximum)
        slider.setFixedWidth(128)
        value = CaptionLabel("", self.details)
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
        """Add one localized brush control row."""

        layout.addWidget(LocalizedCaptionLabel(text), row, 0)
        layout.addWidget(slider, row, 1)
        layout.addWidget(value, row, 2)


__all__ = ["InputBrushSettingsSection"]
