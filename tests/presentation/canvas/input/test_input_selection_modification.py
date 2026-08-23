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

"""Exercise mounted Input selection-modification behavior."""

from __future__ import annotations

from cutecanvas import ExecutionRuntime
from typing import cast

from cutecanvas import (
    CuteCanvas,
    RasterExtentPolicy,
)
from PySide6.QtCore import (
    QPoint,
    QPointF,
    QRect,
    QSize,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QWheelEvent,
)
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
)
import pytest
from qfluentwidgets import themeColor  # type: ignore[import-untyped]

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)
from substitute.presentation.canvas.input.input_selection_contextual_toolbar import (
    InputSelectionContextualToolbarPage,
)
from substitute.presentation.canvas.input.input_selection_modification_contextual_toolbar import (
    InputSelectionModificationContextualToolbarPage,
)
from tests.support.input_canvas.tool_context_projection import (
    project_authored_input_tool_context,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_GAP,
)
from substitute.presentation.widgets import SpinBox
from substitute.presentation.resources.fluent_app_icon import AppIcon


from tests.presentation.canvas.input.input_tool_options_harness import (
    _app,
    _mounted_input,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition, wait_for_qt_signal


def test_modify_selection_previews_original_and_settles_explicitly(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Contextual modification must replace from its base until Apply or Cancel."""
    app = _app()
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        assert canvas.contextual_toolbar.page is None
        assert not canvas.contextual_toolbar.isVisible()
        selection = QImage(20, 16, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(20, 18, 20, 16),
        )
        app.processEvents()

        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        assert page.modify_button.text() == "Modify selection"
        QTest.mouseClick(page.modify_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        modification_page = canvas.contextual_toolbar.page
        assert isinstance(
            modification_page,
            InputSelectionModificationContextualToolbarPage,
        )
        wait_for_qt_condition(modification_page.isVisible)
        controls = modification_page.controls
        assert [
            controls.operation_selector.itemText(index)
            for index in range(controls.operation_selector.count())
        ] == ["Expand", "Contract", "Feather"]
        assert isinstance(controls.pixel_amount, SpinBox)
        assert not controls.pixel_amount.isSymbolVisible()
        assert controls.pixel_amount.maximum() == 999
        assert controls.pixel_amount.width() == 42
        assert controls.pixel_amount.height() == CANVAS_CHROME_CONTROL_HEIGHT
        assert controls.operation_selector.height() == CANVAS_CHROME_CONTROL_HEIGHT
        assert controls.pixel_amount.alignment() == Qt.AlignmentFlag.AlignCenter
        assert modification_page.layout().count() == 2
        assert modification_page.cancel_button.toolTip() == "Cancel"
        assert modification_page.apply_button.toolTip() == "Apply"
        assert modification_page.cancel_button.accessibleName() == "Cancel"
        assert modification_page.apply_button.accessibleName() == "Apply"
        assert modification_page.cancel_button.size() == QSize(
            CANVAS_CHROME_CONTROL_HEIGHT,
            CANVAS_CHROME_CONTROL_HEIGHT,
        )
        assert modification_page.apply_button.size() == QSize(
            CANVAS_CHROME_CONTROL_HEIGHT,
            CANVAS_CHROME_CONTROL_HEIGHT,
        )
        assert modification_page.apply_button.x() < modification_page.cancel_button.x()
        settlement_left = modification_page.settlement_controls.mapTo(
            modification_page,
            modification_page.apply_button.pos(),
        ).x()
        assert (
            settlement_left - modification_page.controls.geometry().right() - 1
            >= CANVAS_CHROME_GAP
        )
        assert modification_page.cancel_button.y() == modification_page.apply_button.y()
        wait_for_qt_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(16, 14, 28, 24)
            )
        )

        controls.operation_selector.setCurrentIndex(1)
        controls.pixel_amount.setValue(2)
        wait_for_qt_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(22, 20, 16, 12)
            )
        )
        wheel_position = controls.pixel_amount.rect().center()
        wheel_event = QWheelEvent(
            QPointF(wheel_position),
            QPointF(controls.pixel_amount.mapToGlobal(wheel_position)),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(controls.pixel_amount, wheel_event)
        assert wheel_event.isAccepted()
        assert controls.pixel_amount.value() == 3
        wait_for_qt_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(23, 21, 14, 10)
            )
        )
        controls.pixel_amount.setValue(2)
        wait_for_qt_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(22, 20, 16, 12)
            )
        )

        QTest.mouseClick(modification_page.cancel_button, Qt.MouseButton.LeftButton)
        wait_for_qt_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(20, 18, 20, 16)
            )
        )
        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        wait_for_qt_condition(page.isVisible)

        QTest.mouseClick(page.modify_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        modification_page = canvas.contextual_toolbar.page
        assert isinstance(
            modification_page,
            InputSelectionModificationContextualToolbarPage,
        )
        wait_for_qt_condition(modification_page.isVisible)
        completed = QSignalSpy(
            canvas.document.canvas.pixelSelectionModificationCompleted
        )
        modification_page.controls.pixel_amount.setValue(5)
        QTest.mouseClick(modification_page.apply_button, Qt.MouseButton.LeftButton)
        wait_for_qt_signal(completed)
        wait_for_qt_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(15, 13, 30, 26)
            )
        )
        assert isinstance(
            canvas.contextual_toolbar.page,
            InputSelectionContextualToolbarPage,
        )
        assert canvas.document.canvas.undoSceneEdit()
        wait_for_qt_condition(
            lambda: (
                canvas.document.canvas.pixelSelectionState().bounds
                == QRect(20, 18, 20, 16)
            )
        )
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_contextual_toolbar_drags_clamps_and_deselects(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Selection chrome must retain movable placement and derive dismissal from state."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, _controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        selection = QImage(12, 12, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(34, 22, 12, 12),
        )
        app.processEvents()

        toolbar = canvas.contextual_toolbar
        page = toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        assert toolbar.drag_handle.cursor().shape() is Qt.CursorShape.ArrowCursor
        assert toolbar.drag_handle.width() < toolbar.drag_handle.height()
        assert toolbar.drag_handle.x() < toolbar.content_host.x()
        pill_image = toolbar.drag_handle.grab().toImage()
        painted_accent = pill_image.pixelColor(pill_image.rect().center())
        expected_accent = QColor(themeColor())
        assert painted_accent.name() == expected_accent.name()
        panel_selection = canvas.document.tool_options.pixel_selection_panel_bounds()
        assert panel_selection is not None
        assert toolbar.geometry().top() > panel_selection.bottom()
        start = toolbar.pos()
        toolbar.drag_handle.dragged.emit(QPoint(30, -70))
        app.processEvents()
        assert toolbar.pos() == start + QPoint(30, -70)

        retained_center = toolbar.geometry().center()
        QTest.mouseClick(page.modify_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert (toolbar.geometry().center() - retained_center).manhattanLength() <= 1
        modification_page = toolbar.page
        assert isinstance(
            modification_page,
            InputSelectionModificationContextualToolbarPage,
        )
        wait_for_qt_condition(modification_page.isVisible)
        QTest.mouseClick(modification_page.cancel_button, Qt.MouseButton.LeftButton)
        wait_for_qt_condition(
            lambda: (
                isinstance(
                    toolbar.page,
                    InputSelectionContextualToolbarPage,
                )
                and bool(toolbar.page is not None and toolbar.page.isVisible())
            )
        )

        toolbar.drag_handle.dragged.emit(QPoint(10_000, 10_000))
        app.processEvents()
        assert canvas.canvas.rect().contains(toolbar.geometry())

        current_page = toolbar.page
        assert isinstance(current_page, InputSelectionContextualToolbarPage)
        deselect = current_page.action_strip.button_for(InputCanvasToolId.DESELECT)
        assert deselect is not None
        deselect_widget = cast(QWidget, deselect)
        wait_for_qt_condition(deselect_widget.isEnabled)
        deselect_widget.setFocus(Qt.FocusReason.MouseFocusReason)
        assert QApplication.focusWidget() is deselect_widget
        QTest.mouseClick(deselect_widget, Qt.MouseButton.LeftButton)
        app.processEvents()
        cleared_selection = canvas.document.canvas.pixelSelectionState()
        assert cleared_selection is not None and not cleared_selection.has_selection
        wait_for_qt_condition(lambda: toolbar.page is None)
        wait_for_qt_condition(lambda: not toolbar.isVisible())
        assert QApplication.focusWidget() is canvas.document.canvas
        QTest.keyPress(canvas.document.canvas, Qt.Key.Key_Space)
        assert (
            canvas.document.canvas.getControlMode() == CuteCanvas.CONTROL_MODE_PANZOOM
        )
        assert not canvas.window().isMinimized()
        QTest.keyRelease(canvas.document.canvas, Qt.Key.Key_Space)
    finally:
        canvas.close()
        destroy_qt_object(canvas)


def test_contextual_toolbar_clear_erases_selected_mask_pixels_without_deselecting(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Clear must edit the active layer while retaining selection context."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas, controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        mask_id = canvas.document.active_mask_id()
        assert mask_id is not None
        mask_pixels = QImage(96, 64, QImage.Format.Format_Grayscale8)
        mask_pixels.fill(0)
        mask_painter = QPainter(mask_pixels)
        mask_painter.fillRect(QRect(34, 22, 12, 12), QColor(255, 255, 255))
        mask_painter.end()
        assert canvas.document.canvas.replaceMaskImage(mask_id, mask_pixels)
        mask_info = canvas.document.canvas.listMasksForComposition()[0]
        assert mask_info.scene_id is not None
        assert mask_info.layer_id is not None
        canvas.document.canvas.setRasterExtentPolicy(
            mask_info.scene_id,
            mask_info.layer_id,
            RasterExtentPolicy.EXPAND_ON_WRITE,
        )
        compacting_selection = QImage(12, 12, QImage.Format.Format_Grayscale8)
        compacting_selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            compacting_selection,
            QRect(34, 22, 12, 12),
        )
        assert canvas.document.canvas.deleteSelectedPixels()
        assert canvas.document.canvas.undoSceneEdit()
        selection = QImage(40, 32, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert canvas.document.canvas.setPixelSelection(
            selection,
            QRect(24, 12, 40, 32),
        )
        project_authored_input_tool_context(controller, canvas.document.tool_context)
        app.processEvents()
        before = canvas.document.export_mask_image(mask_id)
        assert before is not None
        assert before.pixelColor(36, 24).red() == 255
        assert canvas.document.tool_context.snapshot.selection_clear_available
        content_changes = QSignalSpy(canvas.document.maskContentChanged)
        assert canvas.document.tool_options.clear_selected_pixels()
        app.processEvents()
        assert content_changes.count() == 1
        assert canvas.document.canvas.undoSceneEdit()
        app.processEvents()
        assert content_changes.count() == 2
        restored = canvas.document.export_mask_image(mask_id)
        assert restored is not None
        assert restored.pixelColor(36, 24).red() == 255

        page = canvas.contextual_toolbar.page
        assert isinstance(page, InputSelectionContextualToolbarPage)
        clear = page.action_strip.button_for(InputCanvasToolId.CLEAR_SELECTION_PIXELS)
        assert clear is not None
        clear_presentation = controller.palette.presentation_for(
            InputCanvasToolId.CLEAR_SELECTION_PIXELS
        )
        assert clear_presentation is not None
        assert clear_presentation.icon is AppIcon.ERASER_20_REGULAR
        wait_for_qt_condition(clear.isEnabled)
        requested = QSignalSpy(canvas.toolRequested)
        QTest.mouseClick(clear, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert requested.count() == 1
        assert requested.at(0)[0] == InputCanvasToolId.CLEAR_SELECTION_PIXELS
        assert content_changes.count() == 3

        after = canvas.document.export_mask_image(mask_id)
        assert after is not None
        assert after.pixelColor(36, 24).red() == 0
        assert canvas.document.tool_context.snapshot.has_pixel_selection
        assert canvas.contextual_toolbar.isVisible()
    finally:
        canvas.close()
        destroy_qt_object(canvas)
