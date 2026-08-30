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

"""Exercise mounted Input selection interaction behavior."""

from __future__ import annotations

from cutecanvas import ExecutionRuntime

from PySide6.QtCore import (
    QPoint,
    QRect,
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QImage,
)
from PySide6.QtTest import QSignalSpy, QTest
import pytest

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)


from tests.presentation.canvas.input.input_tool_options_harness import (
    _app,
    _mounted_input,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_delete_key_clears_selection_pixels_from_any_active_tool(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Delete should follow selection state instead of the current tool mode."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        mask_pixels = QImage(96, 64, QImage.Format.Format_Grayscale8)
        mask_pixels.fill(255)
        assert canvas.document.canvas.replaceMaskImage(mask_id, mask_pixels)
        selection = QImage(12, 12, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(34, 22, 12, 12),
        )
        app.processEvents()
        content_changes = QSignalSpy(canvas.document.maskContentChanged)

        assert controller.request_tool(InputCanvasToolId.SELECT_RECTANGLE)
        QTest.keyClick(canvas.document.canvas, Qt.Key.Key_Delete)
        app.processEvents()

        cleared = canvas.document.export_mask_image(mask_id)
        assert cleared is not None
        assert cleared.pixelColor(36, 24).red() == 0
        assert content_changes.count() == 1
        assert canvas.document.tool_context.snapshot.has_pixel_selection

        assert canvas.document.canvas.undoSceneEdit()
        app.processEvents()
        assert content_changes.count() == 2
        assert controller.request_tool(InputCanvasToolId.BRUSH)
        QTest.keyClick(canvas.document.canvas, Qt.Key.Key_Delete)
        app.processEvents()

        cleared_from_brush = canvas.document.export_mask_image(mask_id)
        assert cleared_from_brush is not None
        assert cleared_from_brush.pixelColor(36, 24).red() == 0
        assert content_changes.count() == 3
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_contextual_toolbar_hides_during_selection_authoring_and_follows_result(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Selection gestures must hide chrome and remount it below updated bounds."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        selection = QImage(12, 12, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(34, 22, 12, 12),
        )
        app.processEvents()
        toolbar = canvas.contextual_toolbar
        assert toolbar.isVisible()
        old_panel_bounds = canvas.document.tool_options.pixel_selection_panel_bounds()
        assert old_panel_bounds is not None

        assert controller.request_tool(InputCanvasToolId.SELECT_RECTANGLE)
        gesture = canvas.document.canvas.sceneToPanelRect(QRectF(6, 6, 18, 14))
        assert gesture is not None
        QTest.mousePress(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=gesture.topLeft().toPoint(),
        )
        app.processEvents()
        wait_for_qt_condition(lambda: not toolbar.isVisible())
        QTest.mouseMove(canvas.document.canvas, gesture.bottomRight().toPoint())
        QTest.mouseRelease(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=gesture.bottomRight().toPoint(),
        )
        wait_for_qt_condition(toolbar.isVisible)

        new_panel_bounds = canvas.document.tool_options.pixel_selection_panel_bounds()
        assert new_panel_bounds is not None
        assert new_panel_bounds != old_panel_bounds
        assert toolbar.geometry().top() > new_panel_bounds.bottom()
        assert toolbar.geometry().contains(
            QPoint(new_panel_bounds.center().x(), toolbar.geometry().top())
        )

        previous_panel_bounds = QRect(new_panel_bounds)
        canvas.document.canvas.applyZoom(
            canvas.document.canvas.currentZoom() * 1.15,
            canvas.document.canvas.rect().center(),
        )
        app.processEvents()
        zoomed_panel_bounds = (
            canvas.document.tool_options.pixel_selection_panel_bounds()
        )
        assert zoomed_panel_bounds is not None
        assert zoomed_panel_bounds != previous_panel_bounds
        assert toolbar.geometry().top() > zoomed_panel_bounds.bottom()

        pan_start = canvas.document.canvas.rect().center()
        pan_end = pan_start + QPoint(48, 24)
        QTest.keyPress(canvas.document.canvas, Qt.Key.Key_Space)
        QTest.mousePress(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=pan_start,
        )
        QTest.mouseMove(canvas.document.canvas, pan_end)
        QTest.mouseRelease(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=pan_end,
        )
        QTest.keyRelease(canvas.document.canvas, Qt.Key.Key_Space)
        app.processEvents()

        panned_panel_bounds = (
            canvas.document.tool_options.pixel_selection_panel_bounds()
        )
        assert panned_panel_bounds is not None
        assert panned_panel_bounds != zoomed_panel_bounds
        assert toolbar.geometry().top() > panned_panel_bounds.bottom()
        assert toolbar.geometry().contains(
            QPoint(panned_panel_bounds.center().x(), toolbar.geometry().top())
        )
    finally:
        canvas.close()
        destroy_qt_object(canvas)
