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

"""Verify transient zoom feedback through mounted CuteCanvas surfaces."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest
from PySide6.QtCore import (
    QElapsedTimer,
    QEvent,
    QLineF,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPen, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from cutecanvas import (
    CanvasComparisonDivider,
    CanvasComparisonOverlayState,
    CanvasDocument,
    CanvasOverlayState,
    CanvasWorkspace,
    ComparisonOrientation,
    CuteCanvas,
)

from substitute.presentation.canvas.host.floating_canvas_window import (
    FloatingCanvasWindow,
)
from substitute.presentation.canvas.output.output_canvas_zoom_indicators import (
    OutputCanvasZoomIndicators,
)
from substitute.presentation.canvas.shared.canvas_comparison_zoom_indicator import (
    CanvasComparisonZoomIndicator,
)
from substitute.presentation.canvas.shared.canvas_zoom_indicator import (
    CANVAS_ZOOM_INDICATOR_OVERLAY_NAME,
    CanvasZoomIndicator,
    CanvasZoomScale,
)
from substitute.presentation.canvas.shared.canvas_zoom_indicator_layout import (
    CanvasZoomBadge,
    position_zoom_badges,
)
from substitute.presentation.shell.chrome_style import (
    floating_surface_border_color,
    floating_surface_color,
    floating_surface_text_color,
)


def test_zoom_scale_formats_uniform_and_anisotropic_percentages() -> None:
    """Keep scale labels compact without concealing unequal source axes."""

    assert CanvasZoomScale(1.25, 1.25).label() == "125%"
    assert CanvasZoomScale(0.063, 0.063).label() == "6.3%"
    assert CanvasZoomScale(2.0, 1.0).label() == "200% × 100%"


@pytest.mark.parametrize(
    ("position", "expected_texts"),
    (
        (QPointF(100.0, 150.0), ("125%", "83%")),
        (QPointF(600.0, 150.0), ("125%", "83%")),
        (QPointF(399.0, 590.0), ("125%", "83%")),
    ),
)
def test_comparison_badges_stay_in_their_reveal_regions(
    position: QPointF,
    expected_texts: tuple[str, str],
) -> None:
    """Clamp active and passive labels under cursor, divider, and edge pressure."""

    badges = position_zoom_badges(
        QRect(0, 0, 800, 600),
        position,
        _vertical_divider(),
        _badge("125%", width=80.0),
        _badge("83%", width=70.0),
    )

    assert tuple(badge.text for badge in badges) == expected_texts
    assert badges[0].bounds.right() <= 394.0
    assert badges[1].bounds.left() >= 406.0
    assert badges[0].bounds.top() == badges[1].bounds.top()
    assert all(
        QRectF(0.0, 0.0, 800.0, 600.0).contains(badge.bounds) for badge in badges
    )


@pytest.mark.parametrize(
    ("divider_x", "expected_text"),
    ((900.0, "125%"), (-100.0, "83%")),
)
def test_offscreen_comparison_side_keeps_the_visible_badge(
    divider_x: float,
    expected_text: str,
) -> None:
    """Do not suppress the visible label when the other reveal is offscreen."""

    divider = CanvasComparisonDivider(
        enabled=True,
        split_position=0.5,
        orientation=ComparisonOrientation.VERTICAL,
        visible_segment=None,
        full_segment=QLineF(divider_x, 0.0, divider_x, 600.0),
    )

    badges = position_zoom_badges(
        QRect(0, 0, 800, 600),
        QPointF(300.0, 200.0),
        divider,
        _badge("125%", width=60.0),
        _badge("83%", width=54.0),
    )

    assert tuple(badge.text for badge in badges) == (expected_text,)
    assert badges[0].bounds.topLeft() == QPointF(312.0, 212.0)


def test_real_detail_wheel_reports_actual_render_scale_and_tracks_pointer() -> None:
    """Drive a mounted detail view and derive feedback from its render snapshot."""

    app = _application()
    document = CanvasDocument()
    composition_id = document.create_composition_from_image(_image(QSize(320, 240)))
    canvas = CuteCanvas(document=document, features=())
    indicator = CanvasZoomIndicator(canvas)
    observed: list[CanvasOverlayState] = []
    try:
        canvas.resize(640, 480)
        canvas.openComposition(composition_id)
        canvas.show()
        app.processEvents()
        canvas.setZoom1To1()
        app.processEvents()
        initial_zoom = canvas.currentZoom()

        QApplication.sendEvent(canvas, _wheel_event(canvas, QPointF(300.0, 220.0)))

        assert _wait_until(lambda: canvas.currentZoom() > initial_zoom)
        assert indicator.opacity == 1.0
        QApplication.sendEvent(
            canvas,
            _mouse_move_event(canvas, QPointF(420.0, 300.0)),
        )
        canvas.registerCanvasOverlay(
            "test-detail-scale-capture",
            lambda _painter, state: observed.append(state),
        )
        canvas.grab()
        assert observed
        painter = _RecordingPainter()
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
        document.close()
        app.processEvents()


def test_real_detail_double_click_shows_feedback() -> None:
    """Recognize the historical Fit/1:1 double-click as a positioned gesture."""

    app = _application()
    document = CanvasDocument()
    composition_id = document.create_composition_from_image(_image(QSize(200, 120)))
    canvas = CuteCanvas(document=document, features=())
    indicator = CanvasZoomIndicator(canvas)
    try:
        canvas.resize(640, 480)
        canvas.openComposition(composition_id)
        canvas.show()
        app.processEvents()
        initial_zoom = canvas.currentZoom()

        QApplication.sendEvent(
            canvas,
            _double_click_event(canvas, QPointF(260.0, 180.0)),
        )

        assert _wait_until(lambda: canvas.currentZoom() != initial_zoom)
        assert indicator.opacity == 1.0
    finally:
        indicator.close()
        canvas.close()
        document.close()
        app.processEvents()


def test_output_indicator_releases_canvas_after_native_canvas_destruction() -> None:
    """Drop the registry reference without touching an already-deleted canvas."""

    app = _application()
    document = CanvasDocument()
    composition_id = document.create_composition_from_image(_image(QSize(200, 120)))
    workspace = CanvasWorkspace(document=document, features=())
    indicators = OutputCanvasZoomIndicators(workspace)
    try:
        workspace.setSinglePresentation(composition_id)
        app.processEvents()
        canvas = workspace.currentCanvas()
        assert canvas is not None
        assert canvas in indicators._indicators

        canvas.destroyed.disconnect()
        canvas.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        indicators._release_canvas(canvas)

        assert canvas not in indicators._indicators
    finally:
        workspace.close()
        document.close()
        app.processEvents()


@pytest.mark.parametrize("gesture_kind", ("wheel", "double_click"))
def test_real_comparison_gestures_show_independent_source_scales(
    gesture_kind: str,
) -> None:
    """Exercise mounted comparison interaction and its actual two-layer geometry."""

    app = _application()
    document = CanvasDocument()
    primary_id = document.create_composition_from_image(_image(QSize(320, 240)))
    secondary_id = document.create_composition_from_image(_image(QSize(800, 300)))
    workspace = CanvasWorkspace(document=document, features=())
    indicator = CanvasComparisonZoomIndicator(workspace)
    observed: list[CanvasComparisonOverlayState] = []
    try:
        workspace.resize(800, 600)
        workspace.registerComparisonOverlay(
            "test-comparison-scale-capture",
            lambda _painter, state: observed.append(state),
        )
        workspace.setComparisonPresentation(primary_id, secondary_id)
        workspace.show()
        app.processEvents()
        surface = workspace.currentCanvas()
        assert surface is not None
        pointer = QPointF(200.0, 150.0)
        event = (
            _wheel_event(surface, pointer)
            if gesture_kind == "wheel"
            else _double_click_event(surface, pointer)
        )

        QApplication.sendEvent(surface, event)

        assert _wait_until(lambda: indicator.opacity == 1.0)
        surface.grab()
        assert observed
        state = observed[-1]
        painter = _RecordingPainter()
        indicator.draw(painter, state)  # type: ignore[arg-type]
        expected = [
            CanvasZoomScale(
                state.primary_scale.horizontal,
                state.primary_scale.vertical,
            ).label(),
            CanvasZoomScale(
                state.secondary_scale.horizontal,
                state.secondary_scale.vertical,
            ).label(),
        ]
        assert painter.texts == expected
        assert painter.texts[0] != painter.texts[1]
        assert state.divider.visible_segment is not None
        divider_x = state.divider.visible_segment.x1()
        assert painter.rounded_bounds[0].right() < divider_x
        assert painter.rounded_bounds[1].left() > divider_x
    finally:
        indicator.close()
        workspace.close()
        document.close()
        app.processEvents()


def test_floating_detail_uses_the_same_cursor_geometry() -> None:
    """Keep feedback placement independent of the docked or floating host."""

    app = _application()
    document = CanvasDocument()
    composition_id = document.create_composition_from_image(_image(QSize(320, 240)))
    canvas = CuteCanvas(document=document, features=())
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
        app.processEvents()
        canvas.setZoom1To1()
        QApplication.sendEvent(canvas, _wheel_event(canvas, QPointF(300.0, 200.0)))
        assert _wait_until(lambda: indicator.opacity == 1.0)
        QApplication.sendEvent(
            canvas,
            _mouse_move_event(canvas, QPointF(420.0, 280.0)),
        )
        canvas.registerCanvasOverlay(
            "test-floating-scale-capture",
            lambda _painter, state: observed.append(state),
        )
        canvas.grab()
        painter = _RecordingPainter()
        indicator.draw(painter, observed[-1])  # type: ignore[arg-type]

        assert painter.rounded_bounds[0].topLeft() == QPointF(432.0, 292.0)
        assert window.grab().size() == QSize(800, 600)
    finally:
        indicator.close()
        window.close()
        document.close()
        app.processEvents()


def test_new_gesture_restarts_fade_and_uses_output_material() -> None:
    """Restore full opacity for each gesture and retain Output chrome tokens."""

    app = _application()
    document = CanvasDocument()
    composition_id = document.create_composition_from_image(_image(QSize(320, 240)))
    canvas = CuteCanvas(document=document, features=())
    indicator = CanvasZoomIndicator(canvas)
    observed: list[CanvasOverlayState] = []
    try:
        canvas.resize(640, 480)
        canvas.openComposition(composition_id)
        canvas.show()
        app.processEvents()
        canvas.setZoom1To1()
        QApplication.sendEvent(canvas, _wheel_event(canvas, QPointF(100.0, 100.0)))
        assert _wait_until(lambda: indicator.opacity < 1.0 and indicator.opacity > 0.0)

        QApplication.sendEvent(canvas, _wheel_event(canvas, QPointF(120.0, 120.0)))
        assert _wait_until(lambda: indicator.opacity == 1.0)
        canvas.registerCanvasOverlay(
            "test-material-capture",
            lambda _painter, state: observed.append(state),
        )
        canvas.grab()
        painter = _RecordingPainter()
        indicator.draw(painter, observed[-1])  # type: ignore[arg-type]

        assert painter.brushes == [floating_surface_color()]
        assert painter.pens[0].color() == floating_surface_border_color()
        assert painter.text_colors == [floating_surface_text_color()]
        assert _wait_until(lambda: indicator.opacity == 0.0)
    finally:
        indicator.close()
        canvas.close()
        document.close()
        app.processEvents()


def _image(size: QSize) -> QImage:
    """Return an opaque patterned-enough image for mounted rendering."""

    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("cornflowerblue"))
    return image


def _badge(text: str, *, width: float) -> CanvasZoomBadge:
    """Return deterministic badge geometry."""

    return CanvasZoomBadge(text, QRectF(0.0, 0.0, width, 28.0))


def _vertical_divider() -> CanvasComparisonDivider:
    """Return a centered vertical comparison divider."""

    segment = QLineF(400.0, 0.0, 400.0, 600.0)
    return CanvasComparisonDivider(
        enabled=True,
        split_position=0.5,
        orientation=ComparisonOrientation.VERTICAL,
        visible_segment=segment,
        full_segment=segment,
    )


def _wheel_event(target: QWidget, position: QPointF) -> QWheelEvent:
    """Return one local wheel event with a valid global position."""

    return QWheelEvent(
        position,
        QPointF(target.mapToGlobal(position.toPoint())),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def _double_click_event(target: QWidget, position: QPointF) -> QMouseEvent:
    """Return one positioned primary-button double-click event."""

    global_position = QPointF(target.mapToGlobal(position.toPoint()))
    return QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        position,
        global_position,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _mouse_move_event(target: QWidget, position: QPointF) -> QMouseEvent:
    """Return one buttonless local mouse movement."""

    return QMouseEvent(
        QEvent.Type.MouseMove,
        position,
        QPointF(target.mapToGlobal(position.toPoint())),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


class _RecordingPainter:
    """Record visible badge geometry and material assignments."""

    def __init__(self) -> None:
        """Initialize deterministic painter observations."""

        self.texts: list[str] = []
        self.rounded_bounds: list[QRectF] = []
        self.brushes: list[QColor] = []
        self.pens: list[QPen] = []
        self.text_colors: list[QColor] = []
        self._opacity = 1.0

    def save(self) -> None:
        """Accept painter-state saves."""

    def restore(self) -> None:
        """Accept painter-state restores."""

    def opacity(self) -> float:
        """Return the recorded opacity."""

        return self._opacity

    def setOpacity(self, opacity: float) -> None:  # noqa: N802
        """Record painter opacity."""

        self._opacity = opacity

    def setRenderHint(self, *_args: object) -> None:  # noqa: N802
        """Accept render-hint updates."""

    def setFont(self, *_args: object) -> None:  # noqa: N802
        """Accept font updates."""

    def setBrush(self, brush: QColor) -> None:  # noqa: N802
        """Record one fill color."""

        self.brushes.append(QColor(brush))

    def setPen(self, pen: object) -> None:  # noqa: N802
        """Record border pens and text colors."""

        if isinstance(pen, QPen):
            self.pens.append(QPen(pen))
        elif isinstance(pen, QColor):
            self.text_colors.append(QColor(pen))

    def drawRoundedRect(self, bounds: QRectF, *_args: object) -> None:  # noqa: N802
        """Record one badge rectangle."""

        self.rounded_bounds.append(QRectF(bounds))

    def drawText(self, _bounds: object, _alignment: object, text: str) -> None:  # noqa: N802
        """Record one badge label."""

        self.texts.append(text)


def _application() -> QApplication:
    """Return the process Qt application."""

    instance = QApplication.instance()
    return cast(QApplication, instance) if instance is not None else QApplication([])


def _wait_until(predicate: Callable[[], bool], *, timeout_ms: int = 2_000) -> bool:
    """Process Qt work until an observable condition holds or times out."""

    timer = QElapsedTimer()
    timer.start()
    while not predicate() and timer.elapsed() < timeout_ms:
        QTest.qWait(10)
        QApplication.processEvents()
    return predicate()
