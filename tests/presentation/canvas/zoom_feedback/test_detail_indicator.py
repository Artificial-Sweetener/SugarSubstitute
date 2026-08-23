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

"""Test mounted detail-canvas zoom feedback."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSize
from PySide6.QtWidgets import QApplication
from cutecanvas import CanvasDocument, CanvasOverlayState, CuteCanvas, ExecutionRuntime

from substitute.presentation.canvas.host.floating_canvas_window import (
    FloatingCanvasWindow,
)
from substitute.presentation.canvas.shared.canvas_zoom_indicator import (
    CANVAS_ZOOM_INDICATOR_OVERLAY_NAME,
    CanvasZoomIndicator,
    CanvasZoomScale,
)
from substitute.presentation.shell.chrome_style import (
    floating_surface_border_color,
    floating_surface_color,
    floating_surface_text_color,
)
from tests.presentation.canvas.zoom_feedback.support import (
    RecordingPainter,
    double_click_event,
    image,
    mouse_move_event,
    wheel_event,
)
from tests.support.qt.lifecycle import (
    activate_widget_layouts,
    destroy_qt_object,
    ensure_qt_application,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_real_detail_wheel_reports_actual_render_scale_and_tracks_pointer(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Derive mounted detail feedback from its real render snapshot."""

    ensure_qt_application()
    document = CanvasDocument()
    composition_id = document.create_composition_from_image(image(QSize(320, 240)))
    canvas = CuteCanvas(
        document=document,
        features=(),
        execution_runtime=execution_runtime,
    )
    indicator = CanvasZoomIndicator(canvas)
    observed: list[CanvasOverlayState] = []
    try:
        canvas.resize(640, 480)
        canvas.openComposition(composition_id)
        canvas.show()
        wait_for_qt_condition(canvas.isVisible)
        activate_widget_layouts(canvas)
        canvas.setZoom1To1()
        initial_zoom = canvas.currentZoom()

        QApplication.sendEvent(canvas, wheel_event(canvas, QPointF(300.0, 220.0)))

        wait_for_qt_condition(lambda: canvas.currentZoom() > initial_zoom)
        assert indicator.opacity == 1.0
        QApplication.sendEvent(
            canvas,
            mouse_move_event(canvas, QPointF(420.0, 300.0)),
        )
        canvas.registerCanvasOverlay(
            "test-detail-scale-capture",
            lambda _painter, state: observed.append(state),
        )
        canvas.repaint()
        QApplication.processEvents()
        canvas.grab()
        assert observed
        painter = RecordingPainter()
        indicator.draw(painter, observed[-1])  # type: ignore[arg-type]

        scale = observed[-1].display_scale
        assert painter.texts == [
            CanvasZoomScale(scale.horizontal, scale.vertical).label()
        ]
        assert painter.rounded_bounds[0].topLeft() == QPointF(432.0, 312.0)
        assert CANVAS_ZOOM_INDICATOR_OVERLAY_NAME in canvas.contentOverlays()
    finally:
        indicator.close()
        canvas.close()
        destroy_qt_object(canvas)
        document.close()


def test_real_detail_double_click_shows_feedback(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Recognize the historical Fit/1:1 double-click as a positioned gesture."""

    ensure_qt_application()
    document = CanvasDocument()
    composition_id = document.create_composition_from_image(image(QSize(200, 120)))
    canvas = CuteCanvas(
        document=document,
        features=(),
        execution_runtime=execution_runtime,
    )
    indicator = CanvasZoomIndicator(canvas)
    try:
        canvas.resize(640, 480)
        canvas.openComposition(composition_id)
        canvas.show()
        wait_for_qt_condition(canvas.isVisible)
        activate_widget_layouts(canvas)
        initial_zoom = canvas.currentZoom()

        QApplication.sendEvent(
            canvas,
            double_click_event(canvas, QPointF(260.0, 180.0)),
        )

        wait_for_qt_condition(lambda: canvas.currentZoom() != initial_zoom)
        assert indicator.opacity == 1.0
    finally:
        indicator.close()
        canvas.close()
        destroy_qt_object(canvas)
        document.close()


def test_floating_detail_uses_the_same_cursor_geometry(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Keep feedback placement independent of the docked or floating host."""

    ensure_qt_application()
    document = CanvasDocument()
    composition_id = document.create_composition_from_image(image(QSize(320, 240)))
    canvas = CuteCanvas(
        document=document,
        features=(),
        execution_runtime=execution_runtime,
    )
    canvas.openComposition(composition_id)
    window = FloatingCanvasWindow(
        canvas,
        "Output",
        lambda *_args: None,
        backdrop_mode=None,
    )
    indicator = CanvasZoomIndicator(canvas)
    observed: list[CanvasOverlayState] = []
    try:
        window.resize(800, 600)
        window.show()
        wait_for_qt_condition(window.isVisible)
        activate_widget_layouts(window, canvas)
        canvas.setZoom1To1()
        QApplication.sendEvent(canvas, wheel_event(canvas, QPointF(300.0, 200.0)))
        wait_for_qt_condition(lambda: indicator.opacity == 1.0)
        QApplication.sendEvent(
            canvas,
            mouse_move_event(canvas, QPointF(420.0, 280.0)),
        )
        canvas.registerCanvasOverlay(
            "test-floating-scale-capture",
            lambda _painter, state: observed.append(state),
        )
        canvas.repaint()
        QApplication.processEvents()
        canvas.grab()
        painter = RecordingPainter()
        indicator.draw(painter, observed[-1])  # type: ignore[arg-type]

        assert painter.rounded_bounds[0].topLeft() == QPointF(432.0, 292.0)
        assert window.grab().size() == QSize(800, 600)
    finally:
        indicator.close()
        window.close()
        destroy_qt_object(window)
        document.close()


def test_new_gesture_restarts_fade_and_uses_output_material(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Restore full opacity for each gesture and retain Output chrome tokens."""

    ensure_qt_application()
    document = CanvasDocument()
    composition_id = document.create_composition_from_image(image(QSize(320, 240)))
    canvas = CuteCanvas(
        document=document,
        features=(),
        execution_runtime=execution_runtime,
    )
    indicator = CanvasZoomIndicator(canvas)
    observed: list[CanvasOverlayState] = []
    try:
        canvas.resize(640, 480)
        canvas.openComposition(composition_id)
        canvas.show()
        wait_for_qt_condition(canvas.isVisible)
        activate_widget_layouts(canvas)
        canvas.setZoom1To1()
        QApplication.sendEvent(canvas, wheel_event(canvas, QPointF(100.0, 100.0)))
        wait_for_qt_condition(
            lambda: indicator.opacity < 1.0 and indicator.opacity > 0.0
        )

        QApplication.sendEvent(canvas, wheel_event(canvas, QPointF(120.0, 120.0)))
        wait_for_qt_condition(lambda: indicator.opacity == 1.0)
        canvas.registerCanvasOverlay(
            "test-material-capture",
            lambda _painter, state: observed.append(state),
        )
        canvas.repaint()
        QApplication.processEvents()
        canvas.grab()
        painter = RecordingPainter()
        indicator.draw(painter, observed[-1])  # type: ignore[arg-type]

        assert painter.brushes == [floating_surface_color()]
        assert painter.pens[0].color() == floating_surface_border_color()
        assert painter.text_colors == [floating_surface_text_color()]
        wait_for_qt_condition(lambda: indicator.opacity == 0.0)
    finally:
        indicator.close()
        canvas.close()
        destroy_qt_object(canvas)
        document.close()
