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

"""Mount and drive production Input selection-boundary translation."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import QColor, QImage, QMouseEvent
from PySide6.QtWidgets import QApplication
from cutecanvas import CuteCanvas, ExecutionRuntime

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    create_input_canvas_tool_system,
)
from substitute.presentation.canvas.input.input_canvas_tool_controller import (
    InputCanvasToolController,
)
from substitute.presentation.canvas.input.input_canvas_view import InputCanvas
from substitute.presentation.canvas.input.input_contextual_toolbar_installation import (
    install_input_contextual_toolbar,
)
from substitute.presentation.canvas.input.input_tool_options import (
    install_input_tool_options,
)
from tests.support.input_canvas.tool_context_projection import (
    project_authored_input_tool_context,
)
from tests.support.qt.lifecycle import destroy_qt_object


class InputSelectionTranslationHarness:
    """Own one mounted SugarSubstitute Input selection drag."""

    def __init__(self, execution_runtime: ExecutionRuntime) -> None:
        """Mount production Input chrome around one image and mask."""

        self._application()
        self.input_canvas = InputCanvas(execution_runtime=execution_runtime)
        runtime = create_input_canvas_tool_system()
        install_input_tool_options(runtime, self.input_canvas.document.tool_options)
        install_input_contextual_toolbar(
            runtime,
            self.input_canvas.document.tool_options,
        )
        self.tool_controller = InputCanvasToolController(
            transform_activator=(
                self.input_canvas.document.tool_context.activate_transform
            ),
            operation_setter=self.input_canvas.document.set_canvas_operation,
            current_operation_provider=(
                self.input_canvas.document.current_canvas_operation
            ),
            runtime=runtime,
        )
        self.input_canvas.bind_tool_runtime(runtime)
        self.input_canvas.document.tool_context.changed.connect(
            lambda: project_authored_input_tool_context(
                self.tool_controller,
                self.input_canvas.document.tool_context,
            )
        )
        self.input_canvas.document.canvasToolChanged.connect(
            self.tool_controller.synchronize_native_tool
        )
        self.input_canvas.toolRequested.connect(self.tool_controller.request_tool)
        self._install_document()

    @property
    def canvas(self) -> CuteCanvas:
        """Return the production CuteCanvas interaction surface."""

        return self.input_canvas.canvas

    def install_selection(self, bounds: QRect) -> None:
        """Install one opaque selection and activate rectangle selection."""

        coverage = QImage(bounds.size(), QImage.Format.Format_Grayscale8)
        coverage.fill(255)
        if not self.canvas.setPixelSelection(coverage, bounds):
            raise RuntimeError("Mounted Input canvas rejected test selection")
        if not self.input_canvas.document.set_canvas_operation(
            CuteCanvas.CONTROL_MODE_SELECT_RECTANGLE
        ):
            raise RuntimeError("Mounted Input canvas rejected rectangle selection")

    def drag_selection(self, *, start_scene: QPoint, delta: QPoint, steps: int) -> None:
        """Translate the selection through exact synchronous pointer samples."""

        start_panel = self.canvas.sceneToPanelRect(
            QRectF(start_scene.x(), start_scene.y(), 1.0, 1.0)
        )
        if start_panel is None:
            raise RuntimeError("Selection drag start is outside the mounted canvas")
        start = start_panel.center()
        QApplication.sendEvent(
            self.canvas,
            self._mouse_event(
                QEvent.Type.MouseButtonPress,
                start,
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
            ),
        )
        for step in range(1, steps + 1):
            progress = step / steps
            point = QPointF(
                start.x() + delta.x() * progress,
                start.y() + delta.y() * progress,
            )
            QApplication.sendEvent(
                self.canvas,
                self._mouse_event(
                    QEvent.Type.MouseMove,
                    point,
                    Qt.MouseButton.NoButton,
                    Qt.MouseButton.LeftButton,
                ),
            )
        end = QPointF(start.x() + delta.x(), start.y() + delta.y())
        QApplication.sendEvent(
            self.canvas,
            self._mouse_event(
                QEvent.Type.MouseButtonRelease,
                end,
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
            ),
        )

    def close(self) -> None:
        """Release the mounted Input document and queued Qt ownership."""

        self.input_canvas.close()
        destroy_qt_object(self.input_canvas)

    def _install_document(self) -> None:
        """Create one image, one mask, and stable one-to-one scene mapping."""

        image = QImage(512, 512, QImage.Format.Format_ARGB32)
        image.fill(QColor("black"))
        image_id = uuid4()
        self.input_canvas.document.ensure_image_cached(image_id, image, None)
        self.input_canvas.document.set_current_image_id(image_id)
        mask_id = self.input_canvas.document.create_blank_mask(
            image_id,
            QSize(512, 512),
        )
        if mask_id is None:
            raise RuntimeError("Mounted Input canvas could not create a test mask")
        self.input_canvas.document.set_active_mask_id(mask_id)
        project_authored_input_tool_context(
            self.tool_controller,
            self.input_canvas.document.tool_context,
        )
        self.input_canvas.resize(900, 700)
        self.input_canvas.show()
        self.canvas.setZoom1To1()

    def _mouse_event(
        self,
        event_type: QEvent.Type,
        position: QPointF,
        button: Qt.MouseButton,
        buttons: Qt.MouseButton,
    ) -> QMouseEvent:
        """Build one local and globally coherent mouse event."""

        return QMouseEvent(
            event_type,
            QPointF(position),
            QPointF(self.canvas.mapToGlobal(position.toPoint())),
            button,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )

    @staticmethod
    def _application() -> QApplication:
        """Return the application required by the mounted Qt harness."""

        instance = QCoreApplication.instance()
        return instance if isinstance(instance, QApplication) else QApplication([])


__all__ = ["InputSelectionTranslationHarness"]
