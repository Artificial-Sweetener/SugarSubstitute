#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Exercise production contextual Input options through the mounted tool runtime."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication
import pytest

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
    create_input_canvas_tool_system,
)
from substitute.presentation.canvas.input.input_canvas_tool_controller import (
    InputCanvasToolController,
)
from substitute.presentation.canvas.input.input_canvas_view import InputCanvas
from substitute.presentation.canvas.input.input_tool_options import (
    InputBrushOptions,
    InputMaskAdjustmentOptions,
    install_input_tool_options,
)


def _app() -> QApplication:
    """Return the offscreen application used by production widget tests."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _mounted_input() -> tuple[InputCanvas, InputCanvasToolController]:
    """Mount production Input document, toolbar, options, and controller."""

    canvas = InputCanvas()
    runtime = create_input_canvas_tool_system()
    install_input_tool_options(runtime, canvas.document.tool_options)
    controller = InputCanvasToolController(
        input_document=canvas.document,
        operation_setter=canvas.document.set_canvas_operation,
        current_image_id_provider=canvas.document.current_image_id,
        runtime=runtime,
    )
    canvas.bind_tool_runtime(runtime)
    canvas.document.toolContextChanged.connect(controller.refresh_tool_context)
    canvas.document.canvasToolChanged.connect(controller.synchronize_native_tool)
    canvas.toolRequested.connect(controller.request_tool)
    image = QImage(96, 64, QImage.Format.Format_ARGB32)
    image.fill(QColor("black"))
    image_id = uuid4()
    canvas.document.ensure_image_cached(image_id, image, None)
    canvas.document.set_current_image_id(image_id)
    mask_id = canvas.document.create_blank_mask(image_id, QSize(96, 64))
    assert mask_id is not None
    canvas.document.set_active_mask_id(mask_id)
    controller.refresh_tool_context()
    canvas.resize(900, 600)
    canvas.show()
    _app().processEvents()
    return canvas, controller


def test_contextual_options_switch_without_stale_widgets_or_reserved_canvas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Brush and mask controls should follow active tools in a floating surface."""

    app = _app()
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    canvas, controller = _mounted_input()
    try:
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        app.processEvents()
        brush_options = canvas.tool_options_panel.options_widget
        assert isinstance(brush_options, InputBrushOptions)
        assert canvas.tool_options_panel.parentWidget() is canvas.canvas
        assert canvas.canvas.width() == 900
        assert canvas.tool_options_panel.x() > canvas.tool_strip.geometry().right()

        brush_options.size_slider.setValue(173)
        brush_options.hardness_slider.setValue(27)
        brush_options.opacity_slider.setValue(61)
        brush_options.antialias_checkbox.setChecked(True)
        app.processEvents()
        preset = canvas.document.tool_options.brush_preset()
        assert preset.size == 173.0
        assert preset.hardness == 0.27
        assert preset.antialias is True
        assert preset.opacity == 0.61
        pixmap = brush_options.preview.pixmap()
        assert pixmap is not None and not pixmap.isNull()

        assert controller.request_tool(InputCanvasToolId.MASK_RECTANGLE)
        app.processEvents()
        adjustment_options = canvas.tool_options_panel.options_widget
        assert isinstance(adjustment_options, InputMaskAdjustmentOptions)
        assert id(adjustment_options) != id(brush_options)
        adjustment_options.expansion_slider.setValue(13)
        adjustment_options.feather_slider.setValue(7)
        adjustment_options.opacity_slider.setValue(731)
        adjustments = canvas.document.tool_options.active_mask_adjustments()
        assert adjustments is not None
        assert adjustments.expansion == 3.25
        assert adjustments.feather == 1.75
        assert adjustments.opacity == 0.731
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_adjustment_drag_cancels_exactly_when_active_mask_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Erratic layer switching must not commit a preview to the wrong mask."""

    app = _app()
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    canvas, controller = _mounted_input()
    try:
        first_mask_id = canvas.document.active_mask_id()
        image_id = canvas.document.current_image_id()
        assert first_mask_id is not None and image_id is not None
        second_mask_id = canvas.document.create_blank_mask(image_id, QSize(96, 64))
        assert second_mask_id is not None
        assert canvas.document.set_active_mask_id(first_mask_id)
        controller.refresh_tool_context()
        assert controller.request_tool(InputCanvasToolId.MASK_ELLIPSE)
        app.processEvents()
        options = canvas.tool_options_panel.options_widget
        assert isinstance(options, InputMaskAdjustmentOptions)

        options.expansion_slider.sliderPressed.emit()
        options.expansion_slider.setValue(400)
        preview = canvas.document.tool_options.active_mask_adjustments()
        assert preview is not None and preview.expansion == 100.0
        assert canvas.document.set_active_mask_id(second_mask_id)
        app.processEvents()

        first_adjustments = canvas.document.canvas.maskAdjustments(first_mask_id)
        second_adjustments = canvas.document.canvas.maskAdjustments(second_mask_id)
        assert first_adjustments is not None
        assert second_adjustments is not None
        assert first_adjustments.expansion == 0.0
        assert second_adjustments.expansion == 0.0
        assert options.expansion_slider.value() == 0
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()
