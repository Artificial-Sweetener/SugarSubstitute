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

"""Exercise mounted Input contextual transform behavior."""

from __future__ import annotations


from cutecanvas import ExecutionRuntime
from cutecanvas import (
    CuteCanvas,
    EditorTransformTarget,
)
from PySide6.QtCore import (
    QRect,
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QImage,
)
from PySide6.QtTest import QSignalSpy, QTest
import pytest

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)
from substitute.presentation.canvas.input.input_selection_contextual_toolbar import (
    InputSelectionContextualToolbarPage,
)
from substitute.presentation.canvas.input.input_transform_contextual_toolbar import (
    InputTransformContextualToolbarPage,
)
from tests.support.input_canvas.tool_context_projection import (
    project_authored_input_tool_context,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_GAP,
)


from tests.presentation.canvas.input.input_tool_options_harness import (
    _app,
    _mounted_input,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_contextual_transform_requires_explicit_apply_or_cancel(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Selected-pixel transform must morph chrome and settle through one explicit path."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        coverage = QImage(96, 64, QImage.Format.Format_Grayscale8)
        coverage.fill(0)
        for y in range(22, 34):
            for x in range(34, 46):
                coverage.setPixelColor(x, y, QColor(255, 255, 255))
        assert canvas.document.canvas.replaceMaskImage(mask_id, coverage)
        before = canvas.document.export_mask_image(mask_id)
        assert before is not None
        selection = QImage(12, 12, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(34, 22, 12, 12),
        )
        project_authored_input_tool_context(controller, canvas.document.tool_context)
        app.processEvents()

        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        wait_for_qt_condition(page.isVisible)
        transform = page.action_strip.button_for(InputCanvasToolId.TRANSFORM_SELECTION)
        assert transform is not None and transform.isEnabled()
        QTest.mouseClick(transform, Qt.MouseButton.LeftButton)
        app.processEvents()
        transaction = canvas.contextual_toolbar.page
        assert isinstance(transaction, InputTransformContextualToolbarPage)
        wait_for_qt_condition(transaction.isVisible)
        assert transaction.apply_button.toolTip() == "Apply"
        assert transaction.cancel_button.toolTip() == "Cancel"
        assert transaction.apply_button.x() < transaction.cancel_button.x()
        settlement_left = transaction.settlement_controls.mapTo(
            transaction,
            transaction.apply_button.pos(),
        ).x()
        assert (
            settlement_left - transaction.flip_vertical_button.geometry().right() - 1
            >= CANVAS_CHROME_GAP
        )
        assert (
            canvas.document.current_canvas_operation()
            == CuteCanvas.CONTROL_MODE_TRANSFORM
        )
        assert not canvas.tool_strip.isVisible()
        assert not canvas.canvas_top_bar.isVisible()
        assert not transaction.history_controls.undo_button.isEnabled()
        assert transaction.cancel_button.isEnabled()

        cancelled_without_history = QSignalSpy(transaction.cancelRequested)
        QTest.mouseClick(transaction.cancel_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert cancelled_without_history.count() == 1
        assert canvas.edit_sessions.snapshot is None
        assert canvas.document.canvas.floatingPixelEditState() is None
        assert canvas.document.export_mask_image(mask_id) == before
        assert (
            canvas.document.current_canvas_operation()
            != CuteCanvas.CONTROL_MODE_TRANSFORM
        )

        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        wait_for_qt_condition(page.isVisible)
        transform = page.action_strip.button_for(InputCanvasToolId.TRANSFORM_SELECTION)
        assert transform is not None and transform.isEnabled()
        QTest.mouseClick(transform, Qt.MouseButton.LeftButton)
        app.processEvents()
        transaction = canvas.contextual_toolbar.page
        assert isinstance(transaction, InputTransformContextualToolbarPage)
        wait_for_qt_condition(transaction.isVisible)

        start_rect = canvas.document.canvas.sceneToPanelRect(
            QRectF(40.0, 28.0, 1.0, 1.0)
        )
        end_rect = canvas.document.canvas.sceneToPanelRect(QRectF(52.0, 28.0, 1.0, 1.0))
        assert start_rect is not None and end_rect is not None
        start = start_rect.topLeft()
        end = end_rect.topLeft()
        QTest.mousePress(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=start.toPoint(),
        )
        wait_for_qt_condition(lambda: not canvas.contextual_toolbar.isVisible())
        QTest.mouseMove(canvas.document.canvas, end.toPoint())
        QTest.mouseRelease(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=end.toPoint(),
        )
        wait_for_qt_condition(canvas.contextual_toolbar.isVisible)
        assert canvas.document.canvas.floatingPixelEditState() is not None
        transform_bounds = canvas.document.tool_options.transform_panel_bounds(
            EditorTransformTarget.SELECTION_CONTENT
        )
        assert transform_bounds is not None
        assert canvas.contextual_toolbar.geometry().top() > transform_bounds.bottom()
        assert canvas.document.export_mask_image(mask_id) == before
        assert canvas.edit_sessions.snapshot is not None
        assert canvas.edit_sessions.snapshot.can_cancel
        transaction = canvas.contextual_toolbar.page
        assert isinstance(transaction, InputTransformContextualToolbarPage)

        cancelled = QSignalSpy(transaction.cancelRequested)
        QTest.mouseClick(transaction.cancel_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert cancelled.count() == 1
        assert canvas.edit_sessions.snapshot is None
        assert canvas.document.canvas.floatingPixelEditState() is None
        assert canvas.document.export_mask_image(mask_id) == before
        assert (
            canvas.document.current_canvas_operation()
            != CuteCanvas.CONTROL_MODE_TRANSFORM
        )
        assert isinstance(
            canvas.contextual_toolbar.page,
            InputSelectionContextualToolbarPage,
        )

        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        wait_for_qt_condition(page.isVisible)
        transform = page.action_strip.button_for(InputCanvasToolId.TRANSFORM_SELECTION)
        assert transform is not None
        QTest.mouseClick(transform, Qt.MouseButton.LeftButton)
        app.processEvents()
        transaction = canvas.contextual_toolbar.page
        assert isinstance(transaction, InputTransformContextualToolbarPage)
        wait_for_qt_condition(transaction.isVisible)
        QTest.mousePress(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=start.toPoint(),
        )
        QTest.mouseMove(canvas.document.canvas, end.toPoint())
        QTest.mouseRelease(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=end.toPoint(),
        )
        app.processEvents()
        assert canvas.document.canvas.floatingPixelEditState() is not None

        QTest.mouseClick(transaction.apply_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        after = canvas.document.export_mask_image(mask_id)
        assert after is not None and after != before
        assert canvas.document.canvas.floatingPixelEditState() is None
        assert canvas.document.canvas.undoSceneEdit()
        assert canvas.document.export_mask_image(mask_id) == before
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_move_drag_hides_then_reanchors_aligned_toolbar_to_floating_bounds(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Selected-pixel movement must hide chrome and settle against its final frame."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        coverage = QImage(96, 64, QImage.Format.Format_Grayscale8)
        coverage.fill(0)
        for y in range(8, 20):
            for x in range(14, 30):
                coverage.setPixelColor(x, y, QColor(255, 255, 255))
        assert canvas.document.canvas.replaceMaskImage(mask_id, coverage)
        selection = QImage(16, 12, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(14, 8, 16, 12),
        )
        project_authored_input_tool_context(controller, canvas.document.tool_context)
        assert controller.request_tool(InputCanvasToolId.MOVE)
        app.processEvents()
        assert isinstance(
            canvas.contextual_toolbar.page,
            InputSelectionContextualToolbarPage,
        )

        start_rect = canvas.document.canvas.sceneToPanelRect(
            QRectF(20.0, 14.0, 1.0, 1.0)
        )
        end_rect = canvas.document.canvas.sceneToPanelRect(QRectF(34.0, 20.0, 1.0, 1.0))
        assert start_rect is not None and end_rect is not None
        QTest.mousePress(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=start_rect.topLeft().toPoint(),
        )
        wait_for_qt_condition(lambda: not canvas.contextual_toolbar.isVisible())
        QTest.mouseMove(canvas.document.canvas, end_rect.topLeft().toPoint())
        QTest.mouseRelease(
            canvas.document.canvas,
            Qt.MouseButton.LeftButton,
            pos=end_rect.topLeft().toPoint(),
        )
        wait_for_qt_condition(canvas.contextual_toolbar.isVisible)

        floating = canvas.document.canvas.floatingPixelEditState()
        assert floating is not None and not floating.dragging
        floating_bounds = canvas.document.tool_options.floating_pixel_panel_bounds(
            floating
        )
        assert floating_bounds is not None
        assert canvas.contextual_toolbar.geometry().top() > floating_bounds.bottom()
        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        assert page.geometry() == canvas.contextual_toolbar.content_host.rect()
        assert page.modify_button.y() == 0
        assert page.action_strip.y() == 0
        assert page.modify_button.height() == page.action_strip.height()
    finally:
        canvas.close()
        destroy_qt_object(canvas)
