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

"""Verify InputCanvas surface state and compact tool-overlay integration."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QPoint,
    QPointF,
    QRect,
    QSize,
    Qt,
    qInstallMessageHandler,
)
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from cutecanvas import EditorTransformTarget, LayerPolicy
from shiboken6 import isValid

import substitute.presentation.canvas.input.input_canvas_view as input_mod
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    INPUT_CANVAS_CONTEXT_TAGS,
    INPUT_IMAGE_CAPABILITY,
    create_input_canvas_tool_system,
    InputCanvasToolId,
)
from substitute.presentation.canvas.input.input_canvas_tool_controller import (
    InputCanvasToolController,
)
from substitute.presentation.canvas.tools import CanvasToolContext
from substitute.presentation.canvas.shared.contextual_toolbar import (
    ContextualToolbarPage,
)
from tests.support.input_canvas.tool_context_projection import (
    project_authored_input_tool_context,
)

_input_canvas_cutecanvas_features = cast(
    Callable[[], tuple[str, ...]],
    getattr(input_mod, "_input_canvas_cutecanvas_features"),
)


def _app() -> QApplication:
    """Return the shared Qt application for mounted widget assertions."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def test_input_canvas_features_keep_sam_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Input canvas should keep SAM enabled outside diagnostic harness runs."""

    monkeypatch.delenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", raising=False)
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")

    assert _input_canvas_cutecanvas_features() == ("mask", "sam")


def test_input_canvas_features_can_defer_sam_for_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup harness diagnostics may measure Input canvas without eager SAM."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")

    assert _input_canvas_cutecanvas_features() == ("mask",)


def test_input_canvas_destruction_closes_document_before_qt_children(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Destroy the host only after its document closes every CuteCanvas view."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    host = input_mod.InputCanvas()
    document = host.document
    original_close = document.close
    close_observations: list[bool] = []

    def close_document() -> None:
        """Record whether the embedded canvas remains valid at document shutdown."""

        close_observations.append(isValid(host.canvas))
        original_close()

    monkeypatch.setattr(document, "close", close_document)

    host.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()

    assert close_observations == [True]
    assert isValid(host) is False


def test_set_available_false_disables_canvas_tool_chrome_and_shows_overlay() -> None:
    """Unavailable Input state should disable editing without clearing document state."""

    enabled_calls: list[tuple[str, bool]] = []
    overlay_calls: list[tuple[str, object]] = []
    fake = SimpleNamespace(
        canvas=SimpleNamespace(
            setEnabled=lambda value: enabled_calls.append(("canvas", value))
        ),
        _tool_chrome=SimpleNamespace(
            set_enabled=lambda value: enabled_calls.append(("chrome", value))
        ),
        contextual_toolbar=SimpleNamespace(
            setEnabled=lambda value: enabled_calls.append(("contextual", value))
        ),
        _contextual_toolbar_controller=SimpleNamespace(cancel_active_edit=lambda: None),
        _coverage_edit_mode=SimpleNamespace(active=False),
        _availability_overlay=SimpleNamespace(
            setText=lambda text: overlay_calls.append(("text", text)),
            setGeometry=lambda rect: overlay_calls.append(("geometry", rect)),
            raise_=lambda: overlay_calls.append(("raise", None)),
            show=lambda: overlay_calls.append(("show", None)),
            hide=lambda: overlay_calls.append(("hide", None)),
        ),
        rect=lambda: "canvas-rect",
    )

    cast(Any, input_mod.InputCanvas).set_available(fake, False, "No input canvas nodes")

    assert enabled_calls == [
        ("canvas", False),
        ("chrome", False),
        ("contextual", False),
    ]
    assert overlay_calls == [
        ("text", "No input canvas nodes"),
        ("geometry", "canvas-rect"),
        ("raise", None),
        ("show", None),
    ]


def test_set_available_true_enables_canvas_tool_chrome_and_hides_overlay() -> None:
    """Available Input state should restore both canvas and compact tool controls."""

    enabled_calls: list[tuple[str, bool]] = []
    overlay_calls: list[str] = []
    fake = SimpleNamespace(
        canvas=SimpleNamespace(
            setEnabled=lambda value: enabled_calls.append(("canvas", value))
        ),
        _tool_chrome=SimpleNamespace(
            set_enabled=lambda value: enabled_calls.append(("chrome", value))
        ),
        contextual_toolbar=SimpleNamespace(
            setEnabled=lambda value: enabled_calls.append(("contextual", value))
        ),
        _coverage_edit_mode=SimpleNamespace(active=False),
        _availability_overlay=SimpleNamespace(
            hide=lambda: overlay_calls.append("hide")
        ),
    )

    cast(Any, input_mod.InputCanvas).set_available(fake, True)

    assert enabled_calls == [
        ("canvas", True),
        ("chrome", True),
        ("contextual", True),
    ]
    assert overlay_calls == ["hide"]


def test_input_tool_strip_overlays_only_its_content_height(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canvas should retain full width beneath the finite tool strip."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas = input_mod.InputCanvas()
    runtime = create_input_canvas_tool_system()
    palette = runtime.palette
    palette.set_context(
        CanvasToolContext(
            tags=INPUT_CANVAS_CONTEXT_TAGS,
            capabilities=frozenset({INPUT_IMAGE_CAPABILITY}),
        )
    )
    canvas.bind_tool_runtime(runtime)
    canvas.resize(900, 700)
    canvas.show()
    app.processEvents()

    try:
        strip = canvas.tool_strip
        assert strip.parentWidget() is canvas.canvas
        assert strip.x() > 0 and strip.y() > 0
        assert strip.height() == strip.sizeHint().height()
        assert strip.height() < canvas.canvas.height()
        assert canvas.canvas.rect().width() == 900
        assert canvas.canvas.rect().contains(canvas.canvas.rect().bottomRight())
    finally:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()


def test_idle_transform_toolbar_emits_no_qt_paint_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mounted Input transform chrome must not reenter canvas painting while idle."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    host = input_mod.InputCanvas()
    runtime = create_input_canvas_tool_system()
    host.bind_tool_runtime(runtime)
    host.resize(640, 480)
    host.show()
    app.processEvents()
    messages: list[str] = []
    previous_handler = qInstallMessageHandler(
        lambda _kind, _context, message: messages.append(message)
    )
    try:
        image_id = uuid4()
        background = QImage(96, 96, QImage.Format.Format_ARGB32_Premultiplied)
        background.fill(QColor(40, 40, 40, 255))
        assert host.document.ensure_image_cached(image_id, background, None)
        assert host.document.set_current_image_id(image_id)
        raster = QImage(96, 96, QImage.Format.Format_ARGB32_Premultiplied)
        raster.fill(QColor(220, 40, 90, 255))
        layer_id = host.canvas.addEditableRasterLayer(
            raster,
            interaction=LayerPolicy(
                selectable=True,
                movable=True,
                pixel_editable=True,
            ),
        )
        scene = host.canvas.currentScene()
        assert scene is not None and layer_id is not None
        assert host.canvas.setSelectedLayer(scene.scene_id, layer_id)
        selection = QImage(44, 24, QImage.Format.Format_Grayscale8)
        selection.fill(255)
        assert host.canvas.setPixelSelection(selection, QRect(10, 14, 44, 24))
        assert host.document.tool_options.activate_transform(
            EditorTransformTarget.SELECTION_CONTENT
        )
        app.processEvents()
        assert host.contextual_toolbar.isVisible()
        page = host.contextual_toolbar.page
        assert page is not None
        assert host.contextual_toolbar.graphicsEffect() is None
        assert page.graphicsEffect() is None

        geometry_failures: list[str] = []
        elapsed = 0
        while elapsed < 300:
            content_host = host.contextual_toolbar.content_host
            if (
                host.contextual_toolbar.graphicsEffect() is not None
                and content_host.graphicsEffect() is not None
            ):
                geometry_failures.append("nested-shell-and-content-effects")
            for candidate in content_host.findChildren(ContextualToolbarPage):
                if candidate.graphicsEffect() is not None:
                    geometry_failures.append("page-effect-installed")
                if candidate.geometry() != content_host.rect():
                    geometry_failures.append(
                        f"page={candidate.geometry()} host={content_host.rect()}"
                    )
                for control in candidate.findChildren(QWidget):
                    bounds = QRect(control.mapTo(candidate, QPoint()), control.size())
                    if (
                        control.isVisible()
                        and not bounds.isEmpty()
                        and not candidate.rect().contains(bounds)
                    ):
                        geometry_failures.append(
                            f"control={bounds} page={candidate.rect()}"
                        )
            QTest.qWait(5)
            elapsed += 5

        QTest.qWait(900)
        app.processEvents()
        assert host.contextual_toolbar.graphicsEffect() is None
        assert host.contextual_toolbar.content_host.graphicsEffect() is None
        assert page.graphicsEffect() is None
        assert geometry_failures == []

        relevant = [
            message
            for message in messages
            if message.startswith(("QPainter::", "QFont::setPointSize"))
        ]
        assert relevant == []
    finally:
        qInstallMessageHandler(previous_handler)
        host.close()
        host.deleteLater()
        app.processEvents()


def test_input_canvas_resize_preserves_manual_scene_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the inspected pixels and scale fixed through host layout changes."""
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    host = input_mod.InputCanvas()
    image_id = uuid4()
    image = QImage(1600, 1200, QImage.Format.Format_ARGB32)
    image.fill(0xFF404040)
    assert host.document.ensure_image_cached(image_id, image, None)
    assert host.document.set_current_image_id(image_id)
    host.resize(800, 600)
    host.show()
    app.processEvents()
    canvas = host.canvas
    canvas.applyZoom(1.375, anchor=QPointF(275.0, 233.0))
    app.processEvents()

    def projection() -> tuple[float, QPointF, QPointF]:
        """Capture scale and center through CuteCanvas's public hit-test facade."""
        center = QPoint(canvas.width() // 2, canvas.height() // 2)
        center_hit = canvas.panelHitTest(center)
        x_hit = canvas.panelHitTest(center + QPoint(100, 0))
        y_hit = canvas.panelHitTest(center + QPoint(0, 100))
        assert center_hit is not None
        assert x_hit is not None
        assert y_hit is not None
        return (
            canvas.currentZoom(),
            QPointF(center_hit.raw_point),
            QPointF(
                x_hit.raw_point.x() - center_hit.raw_point.x(),
                y_hit.raw_point.y() - center_hit.raw_point.y(),
            ),
        )

    try:
        expected = projection()
        for size in (
            QSize(504, 312),
            QSize(818, 510),
            QSize(130, 98),
            QSize(1202, 908),
            QSize(800, 600),
        ):
            host.resize(size)
            app.processEvents()

            assert projection() == expected
    finally:
        host.close()
        host.deleteLater()
        app.processEvents()


def test_brush_activation_keeps_mounted_tool_strip_alive_and_full_sized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real CuteCanvas Brush transition must not rebuild or collapse its toolbar."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    app = _app()
    canvas = input_mod.InputCanvas()
    runtime = create_input_canvas_tool_system()
    controller = InputCanvasToolController(
        transform_activator=canvas.document.tool_context.activate_transform,
        operation_setter=canvas.document.set_canvas_operation,
        current_operation_provider=canvas.document.current_canvas_operation,
        runtime=runtime,
    )
    canvas.bind_tool_runtime(runtime)
    canvas.document.tool_context.changed.connect(
        lambda: project_authored_input_tool_context(
            controller,
            canvas.document.tool_context,
        )
    )
    canvas.document.canvasToolChanged.connect(controller.synchronize_native_tool)
    canvas.toolRequested.connect(controller.request_tool)
    image_id = uuid4()
    image = QImage(64, 64, QImage.Format.Format_ARGB32)
    image.fill(0xFF404040)
    assert canvas.document.ensure_image_cached(image_id, image, None)
    assert canvas.document.set_current_image_id(image_id)
    mask_id = canvas.document.create_blank_mask(image_id, QSize(64, 64))
    assert mask_id is not None
    assert canvas.document.set_active_mask_id(mask_id)
    project_authored_input_tool_context(controller, canvas.document.tool_context)
    canvas.resize(500, 400)
    canvas.show()
    app.processEvents()
    strip = canvas.tool_strip
    brush = strip.button_for(InputCanvasToolId.BRUSH)
    assert brush is not None
    original_size = strip.size()
    original_buttons = strip.tool_buttons()

    try:
        brush.click()
        assert strip.indicator.animation.state().name == "Running"
        assert strip.indicator.indicator_y != strip.indicator.target_y
        app.processEvents()

        assert strip.isVisibleTo(canvas.canvas)
        assert strip.size() == original_size
        assert strip.width() > 30 and strip.height() > 200
        assert strip.tool_buttons() == original_buttons
        assert strip.button_for(InputCanvasToolId.BRUSH) is brush
        assert strip.indicator.target_y == brush.y() + brush.height() // 2 - 8
        assert controller.palette.active_tool_id == InputCanvasToolId.BRUSH
        canvas.canvas.setCursor(Qt.CursorShape.CrossCursor)
        assert strip.cursor().shape() is Qt.CursorShape.ArrowCursor
        assert canvas.canvas_top_bar.cursor().shape() is Qt.CursorShape.ArrowCursor
        assert canvas.tool_options_host.cursor().shape() is Qt.CursorShape.ArrowCursor
        assert canvas.contextual_toolbar.cursor().shape() is Qt.CursorShape.ArrowCursor
        assert all(
            button.cursor().shape() is Qt.CursorShape.ArrowCursor
            for button in strip.tool_buttons()
        )
        assert all(
            button.geometry().center().x() == strip.rect().center().x()
            for button in strip.tool_buttons()
        )
        stable_buttons = {button.tool_id: button for button in strip.tool_buttons()}
        tool_cycle = (
            InputCanvasToolId.MOVE,
            InputCanvasToolId.MASK_RECTANGLE,
            InputCanvasToolId.MASK_ELLIPSE,
            InputCanvasToolId.MASK_LASSO,
            InputCanvasToolId.BRUSH,
            InputCanvasToolId.PAN_ZOOM,
        )
        for _iteration in range(10):
            for tool_id in tool_cycle:
                button = strip.button_for(tool_id)
                assert button is stable_buttons[tool_id]
                button.click()
                app.processEvents()
                assert strip.size() == original_size
                assert strip.isVisibleTo(canvas.canvas)
                assert strip.button_for(tool_id) is button
                assert controller.palette.active_tool_id == tool_id
                assert strip.indicator.target_y == button.y() + button.height() // 2 - 8
    finally:
        canvas.close()
        canvas.deleteLater()
        runtime.close()
        app.processEvents()


def test_on_image_materialized_relays_host_owned_image_identity() -> None:
    """Document materialization should relay its explicit application identity."""

    image_id = uuid4()
    signal = _Signal()
    fake = SimpleNamespace(inputImageLoaded=signal)

    cast(Any, input_mod.InputCanvas)._on_image_materialized(
        fake, image_id, "E:/images/input.png"
    )

    assert signal.calls == [(image_id, "E:/images/input.png")]


def test_set_canvas_detached_updates_attachment_state() -> None:
    """Input canvas should store locale-neutral attachment state."""

    fake = SimpleNamespace(_canvas_detached=False)

    cast(Any, input_mod.InputCanvas).set_canvas_detached(fake, True)

    assert fake._canvas_detached is True


class _Signal:
    """Record Qt-like signal emissions for relay tests."""

    def __init__(self) -> None:
        """Initialize empty emission history."""

        self.calls: list[tuple[object, ...]] = []

    def emit(self, *args: object) -> None:
        """Record one signal emission."""

        self.calls.append(args)
