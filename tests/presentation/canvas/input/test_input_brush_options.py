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

"""Exercise mounted Input brush-option behavior."""

from __future__ import annotations


from cutecanvas import ExecutionRuntime
from cutecanvas import (
    BrushPreset,
)
from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QPoint,
    QRect,
    Qt,
)
from PySide6.QtGui import (
    QColor,
)
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QPushButton,
    QWidget,
)
import pytest

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)
from substitute.presentation.canvas.input.input_tool_options import (
    InputBrushSettingsControl,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_SURFACE_HEIGHT,
)
from substitute.presentation.canvas.shared.floating_canvas_surface import (
    floating_canvas_surface_stylesheet,
)


from tests.presentation.canvas.input.input_tool_options_harness import (
    _app,
    _mounted_input,
    wait_for_input_tool_chrome_quiescence,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_brush_settings_reflow_and_state_follow_one_top_bar(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Brush settings should expand in order and clear with inactive options."""

    app = _app()
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
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

        QTest.mouseClick(
            brush_settings.brush_settings.header_button,
            Qt.MouseButton.LeftButton,
        )
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

        brush_settings.brush_settings.size_slider.setValue(173)
        brush_settings.brush_settings.hardness_slider.setValue(27)
        brush_settings.brush_settings.opacity_slider.setValue(61)
        app.processEvents()
        preset = canvas.document.tool_options.brush_preset()
        assert preset.size == 173.0
        assert preset.hardness == 0.27
        assert preset.opacity == 0.61
        assert brush_settings.brush_settings.size_value.text() == "173 px"

        assert controller.request_tool(InputCanvasToolId.MASK_RECTANGLE)
        app.processEvents()
        assert canvas.tool_options_host.options_control is None
        assert canvas.tool_options_host.isHidden()
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_brush_settings_preview_tracks_active_layer_color_and_outside_click(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Preview color should follow the active mask and outside clicks should pass."""

    app = _app()
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
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
        preview = brush_settings.brush_settings.preview_image()
        assert not preview.isNull()
        center = preview.pixelColor(preview.width() // 2, preview.height() // 2)
        assert (center.red(), center.green(), center.blue()) == (
            layer_color.red(),
            layer_color.green(),
            layer_color.blue(),
        )

        assert controller.request_tool(InputCanvasToolId.ERASER)
        app.processEvents()
        eraser_settings = canvas.tool_options_host.options_control
        assert isinstance(eraser_settings, InputBrushSettingsControl)
        eraser_preview = eraser_settings.brush_settings.preview_image()
        eraser_center = eraser_preview.pixelColor(
            eraser_preview.width() // 2,
            eraser_preview.height() // 2,
        )
        assert eraser_center == QColor(Qt.GlobalColor.white)

        QTest.mouseClick(
            eraser_settings.brush_settings.header_button,
            Qt.MouseButton.LeftButton,
        )
        app.processEvents()
        assert eraser_settings.expanded

        QTest.mouseClick(
            outside_button,
            Qt.MouseButton.LeftButton,
            pos=QPoint(outside_button.width() // 2, outside_button.height() // 2),
        )
        app.processEvents()
        assert not eraser_settings.expanded
        assert outside_clicks == [True]
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_replaced_brush_settings_release_document_subscriptions(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Removed Brush controls must stop observing document state immediately."""
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        wait_for_input_tool_chrome_quiescence(canvas)
        control = canvas.tool_options_host.options_control
        assert isinstance(control, InputBrushSettingsControl)
        assert control.brush_settings.parent() is control

        assert controller.request_tool(InputCanvasToolId.MASK_RECTANGLE)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        wait_for_input_tool_chrome_quiescence(canvas)

        brush_preset_calls: list[None] = []
        brush_preset = canvas.document.tool_options.brush_preset

        def tracked_brush_preset() -> BrushPreset:
            """Record stale option reads while preserving the real result."""
            brush_preset_calls.append(None)
            return brush_preset()

        monkeypatch.setattr(
            canvas.document.tool_options,
            "brush_preset",
            tracked_brush_preset,
        )
        for _iteration in range(24):
            canvas.document.brushPresetChanged.emit()
        wait_for_input_tool_chrome_quiescence(canvas)

        assert brush_preset_calls == []
    finally:
        canvas.close()
        destroy_qt_object(canvas)
