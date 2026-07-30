#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Render contextual built-in Input tool options over authoritative document state."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol
from uuid import UUID

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QCloseEvent, QImage, QPixmap, QShowEvent
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QWidget
from cutecanvas import BrushPreset, CoverageAdjustments
from qfluentwidgets import CheckBox, CaptionLabel, Slider  # type: ignore[import-untyped]
from sugarsubstitute_shared.presentation.localization import app_text
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    BRUSH_OPTIONS_ID,
    MASK_ADJUSTMENT_OPTIONS_ID,
)
from substitute.presentation.canvas.tools import CanvasToolRuntime


class OptionsSignalPort(Protocol):
    """Describe Qt-compatible signal subscription used by options widgets."""

    def connect(self, callback: object) -> object:
        """Connect one callback."""


class InputToolOptionsDocumentPort(Protocol):
    """Describe brush and mask-adjustment state consumed by contextual controls."""

    brushPresetChanged: OptionsSignalPort
    maskContentChanged: OptionsSignalPort
    toolContextChanged: OptionsSignalPort

    def active_mask_id(self) -> UUID | None:
        """Return the active mask identity."""

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

    def active_mask_adjustments(self) -> CoverageAdjustments | None:
        """Return adjustments for the active mask."""

    def begin_active_mask_adjustment(self) -> bool:
        """Begin one transient adjustment gesture."""

    def preview_active_mask_adjustments(
        self,
        adjustments: CoverageAdjustments,
    ) -> bool:
        """Preview a complete adjustment value."""

    def commit_active_mask_adjustment(self) -> bool:
        """Commit the current adjustment gesture."""

    def cancel_active_mask_adjustment(self) -> bool:
        """Cancel the current adjustment gesture."""


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
        self.antialias_checkbox = CheckBox(app_text("Antialias"), self)
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
        controls.addWidget(self.antialias_checkbox, 3, 1, 1, 2)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.preview)
        layout.addLayout(controls)
        self.size_slider.valueChanged.connect(self._apply_values)
        self.hardness_slider.valueChanged.connect(self._apply_values)
        self.opacity_slider.valueChanged.connect(self._apply_values)
        self.antialias_checkbox.toggled.connect(self._apply_values)
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
            self.antialias_checkbox.setChecked(preset.antialias)
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
                antialias=self.antialias_checkbox.isChecked(),
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


class InputMaskAdjustmentOptions(QWidget):
    """Edit reversible mask-level grow, feather, and coverage opacity."""

    def __init__(
        self,
        document: InputToolOptionsDocumentPort,
        parent: QWidget,
    ) -> None:
        """Build compact controls and guard transactions across context churn."""

        super().__init__(parent)
        self.setObjectName("InputMaskAdjustmentOptions")
        self._document = document
        self._synchronizing = False
        self._gesture_mask_id: UUID | None = None
        self.expansion_slider, self.expansion_value = self._create_slider(
            -4096,
            4096,
        )
        self.feather_slider, self.feather_value = self._create_slider(0, 4096)
        self.opacity_slider, self.opacity_value = self._create_slider(0, 1000)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(4)
        self._add_adjustment_row(
            layout,
            0,
            app_text("Grow / Shrink"),
            self.expansion_slider,
            self.expansion_value,
        )
        self._add_adjustment_row(
            layout,
            1,
            app_text("Feather"),
            self.feather_slider,
            self.feather_value,
        )
        self._add_adjustment_row(
            layout,
            2,
            app_text("Coverage"),
            self.opacity_slider,
            self.opacity_value,
        )
        for slider in (
            self.expansion_slider,
            self.feather_slider,
            self.opacity_slider,
        ):
            slider.sliderPressed.connect(self._begin_gesture)
            slider.valueChanged.connect(self._preview_values)
            slider.sliderReleased.connect(self._commit_gesture)
        document.toolContextChanged.connect(self._context_changed)
        document.maskContentChanged.connect(self._content_changed)
        self.synchronize()

    def synchronize(self) -> None:
        """Project active-mask adjustments and disable stale controls."""

        adjustments = self._document.active_mask_adjustments()
        enabled = adjustments is not None
        self.setEnabled(enabled)
        if adjustments is None:
            return
        self._synchronizing = True
        try:
            self.expansion_slider.setValue(round(adjustments.expansion * 4.0))
            self.feather_slider.setValue(round(adjustments.feather * 4.0))
            self.opacity_slider.setValue(round(adjustments.opacity * 1000.0))
            self._update_value_labels(adjustments)
        finally:
            self._synchronizing = False

    def closeEvent(self, event: QCloseEvent) -> None:
        """Cancel an unfinished gesture before contextual surface teardown."""

        self._cancel_gesture()
        super().closeEvent(event)

    def _begin_gesture(self) -> None:
        """Capture one authoritative mask adjustment before transient previews."""

        if self._gesture_mask_id is not None:
            return
        mask_id = self._document.active_mask_id()
        if mask_id is None or not self._document.begin_active_mask_adjustment():
            return
        self._gesture_mask_id = mask_id

    def _preview_values(self, _value: int) -> None:
        """Preview one complete value, committing keyboard changes atomically."""

        if self._synchronizing:
            return
        transient = self._gesture_mask_id is not None
        if not transient:
            self._begin_gesture()
        if self._gesture_mask_id is None:
            self.synchronize()
            return
        adjustments = self._current_adjustments()
        if not self._document.preview_active_mask_adjustments(adjustments):
            self._cancel_gesture()
            self.synchronize()
            return
        self._update_value_labels(adjustments)
        if not transient:
            self._commit_gesture()

    def _commit_gesture(self) -> None:
        """Commit a matching active-mask gesture as one history edit."""

        mask_id = self._gesture_mask_id
        self._gesture_mask_id = None
        if mask_id is None:
            return
        if self._document.active_mask_id() != mask_id:
            self._document.cancel_active_mask_adjustment()
            self.synchronize()
            return
        self._document.commit_active_mask_adjustment()
        self.synchronize()

    def _cancel_gesture(self) -> None:
        """Restore exact pre-gesture state when context becomes stale."""

        if self._gesture_mask_id is None:
            return
        self._gesture_mask_id = None
        self._document.cancel_active_mask_adjustment()

    def _context_changed(self) -> None:
        """Cancel stale transactions before adopting another mask context."""

        if (
            self._gesture_mask_id is not None
            and self._document.active_mask_id() != self._gesture_mask_id
        ):
            self._cancel_gesture()
        self.synchronize()

    def _content_changed(self) -> None:
        """Refresh after external undo/redo without disrupting this gesture."""

        if self._gesture_mask_id is None:
            self.synchronize()

    def _current_adjustments(self) -> CoverageAdjustments:
        """Build one complete adjustment value from current controls."""

        return CoverageAdjustments(
            expansion=self.expansion_slider.value() / 4.0,
            feather=self.feather_slider.value() / 4.0,
            opacity=self.opacity_slider.value() / 1000.0,
        )

    def _update_value_labels(self, adjustments: CoverageAdjustments) -> None:
        """Render semantic values without confusing overlay and coverage opacity."""

        self.expansion_value.setText(app_text("%1 px", f"{adjustments.expansion:+.2f}"))
        self.feather_value.setText(app_text("%1 px", f"{adjustments.feather:.2f}"))
        self.opacity_value.setText(f"{adjustments.opacity * 100.0:.1f}%")

    def _create_slider(
        self,
        minimum: int,
        maximum: int,
    ) -> tuple[Slider, CaptionLabel]:
        """Create one Fluent slider and fixed-width value label."""

        slider = Slider(Qt.Orientation.Horizontal, self)
        slider.setRange(minimum, maximum)
        slider.setFixedWidth(160)
        value = CaptionLabel("", self)
        value.setMinimumWidth(64)
        return slider, value

    @staticmethod
    def _add_adjustment_row(
        layout: QGridLayout,
        row: int,
        text: str,
        slider: Slider,
        value: CaptionLabel,
    ) -> None:
        """Add one localized mask-adjustment row."""

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
    runtime.register_options(
        MASK_ADJUSTMENT_OPTIONS_ID,
        lambda parent: InputMaskAdjustmentOptions(document, parent),
    )


__all__ = [
    "InputBrushOptions",
    "InputMaskAdjustmentOptions",
    "install_input_tool_options",
]
