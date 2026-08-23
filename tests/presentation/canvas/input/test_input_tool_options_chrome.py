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

"""Exercise mounted Input tool-option chrome behavior."""

from __future__ import annotations

from cutecanvas import ExecutionRuntime

from PySide6.QtCore import (
    QPointF,
    QSize,
    Qt,
    qInstallMessageHandler,
)
from PySide6.QtGui import (
    QColor,
    QImage,
)
from PySide6.QtTest import QTest
import pytest

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)


from tests.presentation.canvas.input.input_tool_options_harness import (
    _LayoutRequestCounter,
    _app,
    _mounted_input,
    wait_for_input_tool_chrome_quiescence,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_empty_mask_disables_layer_transform_until_content_exists(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Mounted Input chrome must follow CuteCanvas meaningful-content state."""
    app = _app()
    canvas, _controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        transform = canvas.tool_strip.button_for(InputCanvasToolId.TRANSFORM_LAYER)
        assert transform is not None
        assert not canvas.document.tool_context.snapshot.layer_transform_available
        assert not transform.isEnabled()
        assert transform.toolTip() == "Nothing to transform!"

        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        coverage = QImage(96, 64, QImage.Format.Format_Grayscale8)
        coverage.fill(0)
        coverage.setPixelColor(20, 20, QColor(255, 255, 255))
        assert canvas.document.canvas.replaceMaskImage(mask_id, coverage)
        app.processEvents()

        transform = canvas.tool_strip.button_for(InputCanvasToolId.TRANSFORM_LAYER)
        assert canvas.document.tool_context.snapshot.layer_transform_available
        assert transform is not None and transform.isEnabled()
        assert transform.toolTip() == "Transform"

        blank = QImage(96, 64, QImage.Format.Format_Grayscale8)
        blank.fill(0)
        assert canvas.document.canvas.replaceMaskImage(mask_id, blank)
        app.processEvents()
        assert not transform.isEnabled()
        assert transform.toolTip() == "Nothing to transform!"

        assert canvas.document.canvas.undoMaskEdit()
        app.processEvents()
        assert transform.isEnabled()
        assert transform.toolTip() == "Transform"

        assert canvas.document.canvas.redoMaskEdit()
        app.processEvents()
        assert not transform.isEnabled()
        assert transform.toolTip() == "Nothing to transform!"
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_top_bar_reaches_idle_quiescence_after_brush_activation(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Canvas chrome must stop scheduling geometry work after one transition."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
    requests = _LayoutRequestCounter()
    canvas.canvas_top_bar.installEventFilter(requests)
    geometry_changes: list[None] = []
    canvas.canvas_top_bar.geometryChanged.connect(lambda: geometry_changes.append(None))
    try:
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        wait_for_input_tool_chrome_quiescence(canvas)
        requests.count = 0
        geometry_changes.clear()

        wait_for_input_tool_chrome_quiescence(canvas)

        assert requests.count == 0
        assert geometry_changes == []
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_mask_stroke_never_reflows_stable_canvas_chrome(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Brush input must remain isolated from Sugar-owned chrome geometry."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
    requests = _LayoutRequestCounter()
    canvas.canvas_top_bar.installEventFilter(requests)
    geometry_changes: list[None] = []
    canvas.canvas_top_bar.geometryChanged.connect(lambda: geometry_changes.append(None))
    try:
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        wait_for_input_tool_chrome_quiescence(canvas)
        start = QPointF(120.0, 240.0)
        finish = QPointF(720.0, 240.0)
        requests.count = 0
        geometry_changes.clear()

        QTest.mousePress(
            canvas.canvas,
            Qt.MouseButton.LeftButton,
            pos=start.toPoint(),
        )
        for step in range(1, 13):
            point = start + (finish - start) * (step / 12.0)
            QTest.mouseMove(canvas.canvas, point.toPoint(), delay=0)
            app.processEvents()
        QTest.mouseRelease(
            canvas.canvas,
            Qt.MouseButton.LeftButton,
            pos=finish.toPoint(),
        )
        wait_for_input_tool_chrome_quiescence(canvas)

        assert requests.count == 0
        assert geometry_changes == []
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_canvas_tool_transitions_settle_without_size_warnings(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Repeated options replacement must quiesce without invalid Qt geometry."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
    messages: list[str] = []
    previous_handler = qInstallMessageHandler(
        lambda _mode, _context, message: messages.append(message)
    )
    try:
        for _iteration in range(20):
            assert controller.request_tool(InputCanvasToolId.BRUSH)
            app.processEvents()
            assert controller.request_tool(InputCanvasToolId.MASK_RECTANGLE)
            app.processEvents()
        wait_for_input_tool_chrome_quiescence(canvas)

        assert not any("Negative sizes" in message for message in messages)
        assert canvas.canvas_top_bar.isHidden()
        assert canvas.canvas_top_bar.size() == QSize(0, 0)
    finally:
        qInstallMessageHandler(previous_handler)
        canvas.close()
        destroy_qt_object(canvas)
