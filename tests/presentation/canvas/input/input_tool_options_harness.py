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

"""Mount deterministic production Input chrome for focused tests."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

from cutecanvas import ExecutionRuntime
from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QObject,
    QPoint,
    QSize,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QRegion,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
)
import pytest

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
import substitute.presentation.canvas.input.input_canvas_context_menu as input_canvas_context_menu
from tests.support.input_canvas.tool_context_projection import (
    project_authored_input_tool_context,
)
from tests.support.qt.semantic_wait import (
    wait_for_qt_condition,
    wait_for_queued_qt_turn,
)
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel


def _app() -> QApplication:
    """Return the offscreen application used by production widget tests."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _request_coverage_from_context_menu(
    monkeypatch: pytest.MonkeyPatch,
    canvas: InputCanvas,
) -> MenuModel:
    """Open the mounted canvas menu and invoke its coverage command."""

    rendered_models: list[MenuModel] = []

    class _RenderedMenu:
        """Capture menu execution without starting a nested Qt event loop."""

        def exec(self, *_args: object, **_kwargs: object) -> None:
            """Accept the rendered menu position without blocking the test."""

    class _Renderer:
        """Capture the production model at the renderer boundary."""

        def __init__(self, *, parent: QWidget) -> None:
            """Retain the expected parent for construction parity."""

            self.parent = parent

        def render(self, model: MenuModel) -> _RenderedMenu:
            """Record one model and return a nonblocking menu surface."""

            rendered_models.append(model)
            return _RenderedMenu()

    monkeypatch.setattr(
        input_canvas_context_menu,
        "QFluentMenuRenderer",
        _Renderer,
    )
    canvas.canvas.customContextMenuRequested.emit(QPoint(12, 12))
    _app().processEvents()

    assert len(rendered_models) == 1
    coverage_action = cast(MenuItem, rendered_models[0].entries[0])
    assert coverage_action.action_id == "input_canvas.edit_layer_coverage"
    assert coverage_action.enabled
    assert coverage_action.callback is not None
    coverage_action.callback()
    _app().processEvents()
    return rendered_models[0]


class _LayoutRequestCounter(QObject):
    """Count layout requests delivered to one observed canvas surface."""

    def __init__(self) -> None:
        """Create an empty request counter."""

        super().__init__()
        self.count = 0

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Record layout requests without affecting delivery."""

        del watched
        if event.type() is QEvent.Type.LayoutRequest:
            self.count += 1
        return False


class _MousePressCounter(QObject):
    """Count mouse presses that reach one canvas receiver's local filters."""

    def __init__(self) -> None:
        """Create an empty press counter."""
        super().__init__()
        self.count = 0

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Record local delivery without consuming the pointer event."""
        del watched
        if event.type() is QEvent.Type.MouseButtonPress:
            self.count += 1
        return False


def wait_for_input_tool_chrome_quiescence(canvas: InputCanvas) -> None:
    """Wait until the tool strip has applied its last deferred projection."""

    def tool_strip_is_quiescent() -> bool:
        """Read the tool strip's authoritative deferred-rebuild state."""

        tool_strip = canvas.tool_strip
        return (
            tool_strip._pending_presentations is None
            and not tool_strip._pending_rebuild_scheduled
        )

    wait_for_qt_condition(tool_strip_is_quiescent)
    wait_for_queued_qt_turn()
    wait_for_qt_condition(tool_strip_is_quiescent)


def _render_without_children(widget: QWidget) -> QImage:
    """Render one widget's own pixels without overlay child controls."""
    image = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    widget.render(
        painter,
        QPoint(),
        QRegion(),
        QWidget.RenderFlag.DrawWindowBackground,
    )
    painter.end()
    return image


def _mounted_input(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> tuple[InputCanvas, InputCanvasToolController]:
    """Mount Input chrome without starting the unrelated native SAM runtime."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    canvas = InputCanvas(execution_runtime=execution_runtime)
    runtime = create_input_canvas_tool_system()
    install_input_tool_options(runtime, canvas.document.tool_options)
    install_input_contextual_toolbar(runtime, canvas.document.tool_options)
    controller = InputCanvasToolController(
        transform_activator=canvas.document.tool_context.activate_transform,
        operation_setter=canvas.document.set_canvas_operation,
        current_operation_provider=canvas.document.current_canvas_operation,
        runtime=runtime,
    )
    canvas.bind_tool_runtime(
        runtime,
        restore_operation=controller.restore_operation,
    )
    canvas.document.tool_context.changed.connect(
        lambda: project_authored_input_tool_context(
            controller,
            canvas.document.tool_context,
        )
    )
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
    project_authored_input_tool_context(controller, canvas.document.tool_context)
    canvas.resize(900, 600)
    canvas.show()
    _app().processEvents()
    canvas.document.canvas.setZoomFit()
    return canvas, controller
