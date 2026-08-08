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

"""Render the shared node-level visual mask opacity control."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from sugarsubstitute_shared.presentation.localization import app_text
from substitute.presentation.localization import LocalizedCaptionLabel
from substitute.presentation.widgets import IntegerSpinnerSlider


class MaskVisualOpacityControl(QWidget):
    """Synchronize one percentage spinner-slider without owning mask layers."""

    opacityChanged = Signal(float)
    opacityCommitted = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the shared visual-opacity row at CuteCanvas's native default."""

        super().__init__(parent)
        self.setObjectName("MaskVisualOpacityControl")
        self._synchronizing = False
        self._committed_opacity = 0.5
        self._edit_origin: float | None = None
        self._slider_edit_active = False
        self.label = LocalizedCaptionLabel(app_text("Visual opacity"), self)
        self.control = IntegerSpinnerSlider(
            minimum=0,
            maximum=100,
            step=1,
            value=50,
            slider_width=132,
            spinbox_width=76,
            suffix="%",
            parent=self,
        )
        self.control.setObjectName("MaskVisualOpacitySpinnerSlider")
        self.control.spinbox.setObjectName("MaskVisualOpacitySpinBox")
        self.control.slider.setObjectName("MaskVisualOpacitySlider")
        self.control.spinbox.setKeyboardTracking(False)
        self.control.slider.installEventFilter(self)
        self.control.valueChanged.connect(self._publish_percentage)
        self.control.slider.sliderPressed.connect(self._begin_slider_edit)
        self.control.slider.sliderReleased.connect(self._finish_slider_edit)
        self.control.spinbox.editingFinished.connect(self._finish_edit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.label)
        layout.addStretch(1)
        layout.addWidget(self.control)

    def opacity(self) -> float:
        """Return the current normalized visual opacity."""

        return self.control.value() / 100.0

    def set_opacity(self, opacity: float) -> None:
        """Project an authoritative normalized value without publishing intent."""

        self._synchronizing = True
        try:
            normalized = min(1.0, max(0.0, opacity))
            self.control.setValue(round(normalized * 100.0))
            self._committed_opacity = normalized
            self._edit_origin = None
            self._slider_edit_active = False
        finally:
            self._synchronizing = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Own complete pointer gestures across Fluent's handle and groove paths."""

        if watched is self.control.slider:
            if event.type() == QEvent.Type.MouseButtonPress:
                self._begin_slider_edit()
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._finish_slider_edit()
        return super().eventFilter(watched, event)

    def _publish_percentage(self, percentage: int) -> None:
        """Publish user-authored normalized opacity exactly once."""

        if not self._synchronizing:
            self._begin_edit()
            self.opacityChanged.emit(percentage / 100.0)
            if not self._slider_edit_active:
                self._finish_edit()

    def _begin_slider_edit(self) -> None:
        """Begin one continuous mouse drag without committing intermediate values."""

        self._slider_edit_active = True
        self._begin_edit()

    def _finish_slider_edit(self) -> None:
        """Commit the final value from one continuous mouse drag."""

        self._slider_edit_active = False
        self._finish_edit()

    def _begin_edit(self) -> None:
        """Capture the value preceding one live spinner or slider gesture."""

        if not self._synchronizing and self._edit_origin is None:
            self._edit_origin = self._committed_opacity

    def _finish_edit(self) -> None:
        """Commit one coalesced gesture after its final live preview value."""

        if self._synchronizing or self._edit_origin is None:
            return
        before = self._edit_origin
        after = self.opacity()
        self._edit_origin = None
        self._committed_opacity = after
        if before != after:
            self.opacityCommitted.emit(before, after)


__all__ = ["MaskVisualOpacityControl"]
