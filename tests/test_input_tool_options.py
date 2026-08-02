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

"""Exercise production contextual Input options through the mounted tool runtime."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget
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
    InputBrushSettingsControl,
    install_input_tool_options,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_SURFACE_HEIGHT,
)
from substitute.presentation.canvas.shared.floating_canvas_surface import (
    floating_canvas_surface_stylesheet,
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


def test_brush_settings_reflow_and_state_follow_one_top_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Brush settings should expand in order and clear with inactive options."""

    app = _app()
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    canvas, controller = _mounted_input()
    try:
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        app.processEvents()
        brush_settings = canvas.tool_options_host.options_control
        assert isinstance(brush_settings, InputBrushSettingsControl)
        assert canvas.canvas_top_bar.parentWidget() is canvas.canvas
        assert canvas.canvas.width() == 900
        assert not brush_settings.expanded
        assert canvas.tool_options_host.height() == CANVAS_CHROME_SURFACE_HEIGHT

        selector_bounds = QRect(8, 8, 84, 36)
        canvas.set_host_chrome_obstacles((selector_bounds,))
        app.processEvents()
        assert canvas.canvas_top_bar.x() == selector_bounds.right() + 9
        assert canvas.canvas_top_bar.y() == selector_bounds.y()
        assert canvas.tool_strip.x() == 8
        assert canvas.tool_strip.y() == selector_bounds.bottom() + 9

        following_control = QWidget(canvas.canvas_top_bar)
        following_control.setFixedSize(24, CANVAS_CHROME_SURFACE_HEIGHT)
        canvas.canvas_top_bar.append_control(following_control)
        following_control.show()
        app.processEvents()
        collapsed_following_x = following_control.x()

        QTest.mouseClick(brush_settings.header_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert brush_settings.expanded
        assert canvas.tool_options_host.height() > CANVAS_CHROME_SURFACE_HEIGHT
        assert following_control.x() > collapsed_following_x
        details = brush_settings.findChild(QWidget, "InputBrushSettingsDetails")
        assert details is not None and details.layout() is not None
        details_margins = details.layout().contentsMargins()
        assert (
            details_margins.left(),
            details_margins.top(),
            details_margins.right(),
            details_margins.bottom(),
        ) == (8, 8, 8, 8)

        QTest.mouseClick(brush_settings.close_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert not brush_settings.expanded
        assert following_control.x() == collapsed_following_x

        canvas.set_host_chrome_obstacles(())
        app.processEvents()
        assert canvas.canvas_top_bar.x() == 8
        assert canvas.tool_strip.x() == 8
        assert canvas.tool_strip.y() == canvas.canvas_top_bar.geometry().bottom() + 9

        assert canvas.tool_strip.styleSheet() == floating_canvas_surface_stylesheet(
            "QFrame#CanvasToolStrip"
        )
        assert (
            canvas.tool_options_host.styleSheet()
            == floating_canvas_surface_stylesheet("QFrame#CanvasToolOptionsHost")
        )

        brush_settings.size_slider.setValue(173)
        brush_settings.hardness_slider.setValue(27)
        brush_settings.opacity_slider.setValue(61)
        app.processEvents()
        preset = canvas.document.tool_options.brush_preset()
        assert preset.size == 173.0
        assert preset.hardness == 0.27
        assert preset.opacity == 0.61
        assert brush_settings.size_value.text() == "173 px"

        assert controller.request_tool(InputCanvasToolId.MASK_RECTANGLE)
        app.processEvents()
        assert canvas.tool_options_host.options_control is None
        assert canvas.tool_options_host.isHidden()
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_brush_settings_preview_tracks_active_layer_color_and_outside_click(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preview color should follow the active mask and outside clicks should pass."""

    app = _app()
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    canvas, controller = _mounted_input()
    outside_button = QPushButton("outside", canvas.canvas)
    outside_button.setGeometry(700, 500, 100, 30)
    outside_button.show()
    outside_clicks: list[bool] = []
    outside_button.clicked.connect(lambda: outside_clicks.append(True))
    try:
        active_mask_id = canvas.document.active_mask_id()
        assert active_mask_id is not None
        layer_color = QColor(231, 45, 137)
        assert canvas.document.set_mask_properties(active_mask_id, color=layer_color)
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        app.processEvents()

        brush_settings = canvas.tool_options_host.options_control
        assert isinstance(brush_settings, InputBrushSettingsControl)
        preview = brush_settings.preview_image()
        assert not preview.isNull()
        center = preview.pixelColor(preview.width() // 2, preview.height() // 2)
        assert (center.red(), center.green(), center.blue()) == (
            layer_color.red(),
            layer_color.green(),
            layer_color.blue(),
        )

        QTest.mouseClick(brush_settings.header_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert brush_settings.expanded

        QTest.mouseClick(
            outside_button,
            Qt.MouseButton.LeftButton,
            pos=QPoint(outside_button.width() // 2, outside_button.height() // 2),
        )
        app.processEvents()
        assert not brush_settings.expanded
        assert outside_clicks == [True]
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()
