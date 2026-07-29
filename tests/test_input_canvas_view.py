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
from PySide6.QtCore import QCoreApplication, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

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

    assert enabled_calls == [("canvas", False), ("chrome", False)]
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
        _availability_overlay=SimpleNamespace(
            hide=lambda: overlay_calls.append("hide")
        ),
    )

    cast(Any, input_mod.InputCanvas).set_available(fake, True)

    assert enabled_calls == [("canvas", True), ("chrome", True)]
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
    canvas.bind_tool_palette(palette)
    canvas.resize(900, 700)
    canvas.show()
    app.processEvents()

    try:
        strip = canvas.tool_strip
        assert strip.parentWidget() is canvas.canvas
        assert strip.x() > 0 and strip.y() > 0
        assert strip.height() < canvas.canvas.height() // 2
        assert canvas.canvas.rect().width() == 900
        assert canvas.canvas.rect().contains(canvas.canvas.rect().bottomRight())
    finally:
        canvas.close()
        canvas.deleteLater()
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
        input_document=canvas.document,
        control_mode_setter=canvas.document.set_canvas_tool_mode,
        current_image_id_provider=canvas.document.current_image_id,
        runtime=runtime,
    )
    canvas.bind_tool_palette(runtime.palette)
    canvas.document.toolContextChanged.connect(controller.refresh_tool_context)
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
    controller.refresh_tool_context()
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
        assert strip.cursor().shape() is Qt.CursorShape.ArrowCursor
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
