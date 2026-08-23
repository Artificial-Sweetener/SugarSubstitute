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

"""Exercise mounted Input layer transform and coverage behavior."""

from __future__ import annotations

from cutecanvas import ExecutionRuntime

from cutecanvas import (
    CuteCanvas,
    EditorIntent,
    EditorTransformTarget,
)
from PySide6.QtCore import (
    QEvent,
    QPoint,
    QPointF,
    QRect,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QImage,
    QMouseEvent,
)
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import (
    QApplication,
)
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
from substitute.presentation.widgets.menu_model import MenuItem


from tests.presentation.canvas.input.input_tool_options_harness import (
    _MousePressCounter,
    _app,
    _mounted_input,
    _render_without_children,
    _request_coverage_from_context_menu,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition, wait_for_qt_signal


def test_layer_transform_uses_tight_content_frame_and_contextual_settlement(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Route toolbar layer transforms through the shared live-frame surface."""

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
        before = canvas.document.export_mask_image(mask_id)
        assert before is not None
        assert not canvas.document.tool_context.snapshot.has_pixel_selection

        project_authored_input_tool_context(controller, canvas.document.tool_context)
        presentation = controller.palette.presentation_for(
            InputCanvasToolId.TRANSFORM_LAYER
        )
        assert presentation is not None and presentation.enabled
        initial_state = canvas.document.canvas.editorTransformState(
            EditorTransformTarget.LAYER_CONTENT
        )
        assert initial_state.allowed, initial_state.denial
        assert controller.request_tool(InputCanvasToolId.TRANSFORM_LAYER)
        app.processEvents()

        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputTransformContextualToolbarPage)
        state = canvas.document.canvas.editorTransformState(
            EditorTransformTarget.LAYER_CONTENT
        )
        assert state.allowed and state.corners is not None
        assert canvas.edit_sessions.snapshot is None
        assert not page.history_controls.undo_button.isEnabled()
        assert not page.history_controls.redo_button.isEnabled()
        assert not page.apply_button.isEnabled()
        assert page.cancel_button.isEnabled()

        cancelled_without_history = QSignalSpy(page.cancelRequested)
        QTest.mouseClick(page.cancel_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert cancelled_without_history.count() == 1
        assert canvas.edit_sessions.snapshot is None
        assert (
            canvas.document.current_canvas_operation()
            != CuteCanvas.CONTROL_MODE_TRANSFORM
        )
        wait_for_qt_condition(lambda: canvas.contextual_toolbar.page is None)

        assert controller.request_tool(InputCanvasToolId.TRANSFORM_LAYER)
        app.processEvents()
        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputTransformContextualToolbarPage)
        panel_bounds = canvas.document.tool_options.transform_panel_bounds(
            EditorTransformTarget.LAYER_CONTENT
        )
        assert panel_bounds is not None
        assert canvas.contextual_toolbar.geometry().top() > panel_bounds.bottom()
        assert not canvas.tool_strip.isVisible()
        assert not canvas.canvas_top_bar.isVisible()

        QTest.mouseClick(page.rotate_right_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert canvas.document.export_mask_image(mask_id) == before
        assert canvas.edit_sessions.snapshot is not None
        assert canvas.edit_sessions.snapshot.can_cancel
        assert page is canvas.contextual_toolbar.page
        assert page.history_controls.undo_button.isEnabled()
        assert not page.history_controls.redo_button.isEnabled()

        QTest.mouseClick(
            page.history_controls.undo_button,
            Qt.MouseButton.LeftButton,
        )
        app.processEvents()
        assert canvas.edit_sessions.snapshot is not None
        assert canvas.edit_sessions.snapshot.undo_depth == 0
        assert canvas.edit_sessions.snapshot.redo_depth == 1
        assert not page.history_controls.undo_button.isEnabled()
        assert page.history_controls.redo_button.isEnabled()
        assert canvas.document.export_mask_image(mask_id) == before

        QTest.mouseClick(
            page.history_controls.redo_button,
            Qt.MouseButton.LeftButton,
        )
        app.processEvents()
        assert canvas.edit_sessions.snapshot is not None
        assert canvas.edit_sessions.snapshot.undo_depth == 1
        assert canvas.edit_sessions.snapshot.redo_depth == 0
        assert page.history_controls.undo_button.isEnabled()
        assert not page.history_controls.redo_button.isEnabled()

        cancelled = QSignalSpy(page.cancelRequested)
        QTest.mouseClick(page.cancel_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert cancelled.count() == 1
        assert canvas.edit_sessions.snapshot is None
        assert canvas.document.export_mask_image(mask_id) == before
        assert (
            canvas.document.current_canvas_operation()
            != CuteCanvas.CONTROL_MODE_TRANSFORM
        )
        wait_for_qt_condition(lambda: canvas.contextual_toolbar.page is None)
        assert canvas.contextual_toolbar.page is None
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_contextual_transform_rejects_selection_without_active_mask_pixels(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Never advertise a selection transform that would target the whole mask."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        coverage = QImage(96, 64, QImage.Format.Format_Grayscale8)
        coverage.fill(0)
        for y in range(6, 18):
            for x in range(6, 18):
                coverage.setPixelColor(x, y, QColor(255, 255, 255))
        assert canvas.document.canvas.replaceMaskImage(mask_id, coverage)
        selection = QImage(12, 12, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(68, 40, 12, 12),
        )

        project_authored_input_tool_context(controller, canvas.document.tool_context)
        app.processEvents()

        assert not canvas.document.tool_context.snapshot.selection_transform_available
        state = canvas.document.canvas.editorOperationState(EditorIntent.TRANSFORM)
        assert not state.allowed
        assert state.denial == "no-selected-pixels"
        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        transform = page.action_strip.button_for(InputCanvasToolId.TRANSFORM_SELECTION)
        assert transform is not None and not transform.isEnabled()
        previous_operation = canvas.document.current_canvas_operation()
        assert not controller.request_tool(InputCanvasToolId.TRANSFORM_SELECTION)
        assert canvas.document.current_canvas_operation() == previous_operation
        assert isinstance(
            canvas.contextual_toolbar.page,
            InputSelectionContextualToolbarPage,
        )
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_real_selection_tools_use_selection_modes_without_mask_capability(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Rectangle, ellipse, and lasso selection tools must be first-class modes."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        for tool_id in (
            InputCanvasToolId.SELECT_RECTANGLE,
            InputCanvasToolId.SELECT_ELLIPSE,
            InputCanvasToolId.SELECT_LASSO,
        ):
            presentation = controller.palette.presentation_for(tool_id)
            assert presentation is not None and presentation.enabled
            assert controller.request_tool(tool_id)
            app.processEvents()
            assert controller.palette.active_tool_id == tool_id
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_layer_coverage_editor_previews_exclusively_and_commits_only_on_apply(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Layer coverage must use one exclusive preview with explicit settlement."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, _controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        coverage = QImage(96, 64, QImage.Format.Format_Grayscale8)
        coverage.fill(0)
        for y in range(24, 40):
            for x in range(40, 56):
                coverage.setPixelColor(x, y, QColor(255, 255, 255))
        assert canvas.document.canvas.replaceMaskImage(mask_id, coverage)
        before = canvas.document.export_mask_image(mask_id)
        assert before is not None
        canvas.document.canvas.setCursor(Qt.CursorShape.CrossCursor)
        completed = QSignalSpy(canvas.document.canvas.layerEdgeModificationCompleted)
        rendered_before = _render_without_children(canvas.document.canvas)
        press_counter = _MousePressCounter()
        canvas.document.canvas.installEventFilter(press_counter)
        menu_model = _request_coverage_from_context_menu(monkeypatch, canvas)
        assert all(
            not entry.action_id.startswith("canvas.tool.")
            for entry in menu_model.entries
            if isinstance(entry, MenuItem)
        )

        editor = canvas.coverage_editor
        assert canvas.coverage_edit_active
        assert editor.isVisible()
        assert not canvas.tool_strip.isVisible()
        assert not canvas.canvas_top_bar.isVisible()
        assert (
            abs(editor.geometry().center().x() - canvas.canvas.rect().center().x()) <= 1
        )
        assert editor.geometry().bottom() == canvas.canvas.height() - 9
        assert editor.controls.operation_selector.itemText(0) == "Expand"
        assert editor.controls.operation_selector.itemText(1) == "Contract"
        assert editor.controls.operation_selector.itemText(2) == "Feather"
        assert editor.controls.pixel_amount.value() == 4

        context_menu_requests = QSignalSpy(
            canvas.document.canvas.customContextMenuRequested
        )
        blocked_context_menu = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            QPoint(20, 20),
            canvas.document.canvas.mapToGlobal(QPoint(20, 20)),
        )
        QApplication.sendEvent(canvas.document.canvas, blocked_context_menu)
        assert blocked_context_menu.isAccepted()
        assert context_menu_requests.count() == 0

        blocked_press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(20.0, 20.0),
            QPointF(canvas.document.canvas.mapToGlobal(QPoint(20, 20))),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(canvas.document.canvas, blocked_press)
        assert press_counter.count == 0

        editor.controls.pixel_amount.setValue(2)
        wait_for_qt_condition(
            lambda: _render_without_children(canvas.document.canvas) != rendered_before
        )
        assert completed.count() == 0
        assert canvas.document.export_mask_image(mask_id) == before

        QTest.mouseClick(editor.apply_button, Qt.MouseButton.LeftButton)
        wait_for_qt_signal(completed)
        app.processEvents()
        after = canvas.document.export_mask_image(mask_id)
        assert after is not None and after != before
        assert not canvas.coverage_edit_active
        assert not editor.isVisible()
        assert canvas.tool_strip.isVisible()
        assert canvas.document.canvas.undoMaskEdit()
        assert canvas.document.export_mask_image(mask_id) == before

        _request_coverage_from_context_menu(monkeypatch, canvas)
        assert canvas.coverage_edit_active
        editor.controls.pixel_amount.setValue(3)
        QTest.mouseClick(editor.close_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert not canvas.coverage_edit_active
        assert canvas.document.export_mask_image(mask_id) == before

        _request_coverage_from_context_menu(monkeypatch, canvas)
        assert canvas.coverage_edit_active
        editor.controls.pixel_amount.setValue(2)
        canvas.close()
        app.processEvents()
        assert not canvas.coverage_edit_active
        assert canvas.document.export_mask_image(mask_id) == before
    finally:
        canvas.close()
        destroy_qt_object(canvas)
