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
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap, QShowEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from cutecanvas import BrushPreset
from qfluentwidgets import (  # type: ignore[import-untyped]
    CaptionLabel,
    FluentIcon,
    SegmentedItem,
    Slider,
    TransparentToolButton,
)
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    apply_application_text,
    set_localized_accessible_name,
    set_localized_tooltip,
)
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    BRUSH_OPTIONS_ID,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_GAP,
)
from substitute.presentation.canvas.tools import (
    CanvasToolOptionsControl,
    CanvasToolRuntime,
)
from substitute.presentation.localization import LocalizedCaptionLabel


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

    def brush_preview_color(self) -> QColor:
        """Return the detached color of the active editable layer."""

    def render_brush_tip_preview(
        self,
        logical_size: QSize,
        *,
        device_pixel_ratio: float,
        color: QColor,
    ) -> QImage:
        """Render a DPR-aware brush-tip image."""


_BRUSH_PREVIEW_SIZE = QSize(20, 20)
_HEADER_MINIMUM_WIDTH = 132


class InputBrushSettingsControl(CanvasToolOptionsControl):
    """Present compact and expanded brush settings from authoritative state."""

    def __init__(
        self,
        document: InputToolOptionsDocumentPort,
        parent: QWidget,
    ) -> None:
        """Build one persistent header and collapsible detailed controls."""

        super().__init__(parent)
        self.setObjectName("InputBrushSettingsControl")
        self._document = document
        self._synchronizing = False
        self._preview_image = QImage()

        self.header_button = SegmentedItem("", self)
        self.header_button.setObjectName("InputBrushSettingsHeader")
        self.header_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_button.setFixedHeight(CANVAS_CHROME_CONTROL_HEIGHT)
        self.header_button.setMinimumWidth(_HEADER_MINIMUM_WIDTH)
        self.header_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.header_button.setIconSize(_BRUSH_PREVIEW_SIZE)
        apply_application_text(self.header_button, app_text("Brush settings"))
        self.header_button.clicked.connect(self.expand)

        self.close_button = TransparentToolButton(FluentIcon.CLOSE, self)
        self.close_button.setObjectName("InputBrushSettingsCloseButton")
        self.close_button.setFixedSize(
            CANVAS_CHROME_CONTROL_HEIGHT,
            CANVAS_CHROME_CONTROL_HEIGHT,
        )
        set_localized_tooltip(self.close_button, "Close")
        set_localized_accessible_name(self.close_button, "Close")
        self.close_button.clicked.connect(self.collapse)
        self.close_button.hide()

        self._details = QWidget(self)
        self._details.setObjectName("InputBrushSettingsDetails")
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
        controls = QGridLayout(self._details)
        controls.setContentsMargins(
            CANVAS_CHROME_GAP,
            CANVAS_CHROME_GAP,
            CANVAS_CHROME_GAP,
            CANVAS_CHROME_GAP,
        )
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
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        header_layout.addWidget(self.header_button)
        header_layout.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(CANVAS_CHROME_GAP // 2)
        layout.addLayout(header_layout)
        layout.addWidget(self._details)
        self._details.hide()

        self.size_slider.valueChanged.connect(self._apply_values)
        self.hardness_slider.valueChanged.connect(self._apply_values)
        self.opacity_slider.valueChanged.connect(self._apply_values)
        document.brushPresetChanged.connect(self.synchronize)
        document.toolContextChanged.connect(self.synchronize)
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
        self._refresh_preview()

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh physical-density-dependent preview when shown."""

        super().showEvent(event)
        self._refresh_preview()

    def apply_expanded_state(self, expanded: bool) -> None:
        """Keep the header stable while exposing or hiding detailed controls."""

        self.close_button.setVisible(expanded)
        self._details.setVisible(expanded)
        self.adjustSize()

    def preview_image(self) -> QImage:
        """Return the detached rendered preview used by the compact header."""

        return QImage(self._preview_image)

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
            color=self._document.brush_preview_color(),
        )
        self._preview_image = QImage(image)
        self.header_button.setIcon(QIcon(QPixmap.fromImage(image)))

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
        value = CaptionLabel("", self._details)
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

        layout.addWidget(LocalizedCaptionLabel(text), row, 0)
        layout.addWidget(slider, row, 1)
        layout.addWidget(value, row, 2)


def install_input_tool_options(
    runtime: CanvasToolRuntime,
    document: InputToolOptionsDocumentPort,
) -> None:
    """Register built-in Input option surfaces through the runtime boundary."""

    runtime.register_options(
        BRUSH_OPTIONS_ID,
        lambda parent: InputBrushSettingsControl(document, parent),
    )


__all__ = [
    "InputBrushSettingsControl",
    "install_input_tool_options",
]
