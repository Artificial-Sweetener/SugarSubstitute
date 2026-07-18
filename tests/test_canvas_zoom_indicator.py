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

"""Verify transient cursor-relative zoom feedback over QPane's public API."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import uuid4

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
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPen, QTransform, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from qpane import (
    ComparisonDividerState,
    ComparisonOrientation,
    Config,
    OverlayState,
    QPane,
)

from substitute.presentation.canvas.host.floating_canvas_window import (
    FloatingCanvasWindow,
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
    """Scale labels should stay brief without concealing distorted axes."""

    assert CanvasZoomScale(1.25, 1.25).label() == "125%"
    assert CanvasZoomScale(0.063, 0.063).label() == "6.3%"
    assert CanvasZoomScale(2.0, 1.0).label() == "200% × 100%"


def test_indicator_registers_and_only_shows_for_positioned_user_zoom() -> None:
    """Programmatic zooms should stay hidden until a positioned gesture changes scale."""

    _application()
    pane = QPane(features=())
    pane.setMouseTracking(False)
    indicator = CanvasZoomIndicator(pane)
    try:
        assert CANVAS_ZOOM_INDICATOR_OVERLAY_NAME in pane.contentOverlays()
        assert pane.hasMouseTracking() is True
        pane.zoomChanged.emit(1.25)
        assert indicator.opacity == 0.0

        _arm_wheel(indicator, pane, QPointF(140.0, 180.0))
        pane.zoomChanged.emit(1.5)
        assert indicator.opacity == 1.0
    finally:
        indicator.close()
        assert pane.hasMouseTracking() is False
        pane.close()

    assert CANVAS_ZOOM_INDICATOR_OVERLAY_NAME not in pane.contentOverlays()


def test_normal_badge_appears_below_cursor_and_clamps_to_canvas() -> None:
    """Normal feedback should follow the gesture without escaping canvas edges."""

    canvas = QRect(0, 0, 800, 600)
    badge = _badge("125%", width=60.0)

    centered = position_zoom_badges(canvas, QPointF(100.0, 150.0), None, badge)
    edge = position_zoom_badges(canvas, QPointF(799.0, 599.0), None, badge)

    assert centered[0].bounds.topLeft() == QPointF(112.0, 162.0)
    assert QRectF(canvas).contains(edge[0].bounds)
    assert edge[0].bounds.right() <= 796.0
    assert edge[0].bounds.bottom() <= 596.0


def test_vertical_compare_cursor_on_base_pairs_at_divider_and_same_y() -> None:
    """The passive comparison badge should meet its divider side at cursor height."""

    badges = position_zoom_badges(
        QRect(0, 0, 800, 600),
        QPointF(100.0, 150.0),
        _vertical_divider(),
        _badge("125%", width=60.0),
        _badge("83%", width=54.0),
    )

    assert [badge.text for badge in badges] == ["125%", "83%"]
    assert badges[0].bounds.topLeft() == QPointF(112.0, 162.0)
    assert badges[1].bounds.left() == 406.0
    assert badges[1].bounds.top() == badges[0].bounds.top()


def test_vertical_compare_cursor_on_comparison_reverses_active_placement() -> None:
    """The base badge should meet the divider when comparison owns the cursor."""

    badges = position_zoom_badges(
        QRect(0, 0, 800, 600),
        QPointF(600.0, 150.0),
        _vertical_divider(),
        _badge("125%", width=60.0),
        _badge("83%", width=54.0),
    )

    assert badges[0].bounds.right() == 394.0
    assert badges[1].bounds.topLeft() == QPointF(612.0, 162.0)
    assert badges[0].bounds.top() == badges[1].bounds.top()


def test_horizontal_compare_rotates_cursor_and_divider_pairing() -> None:
    """Horizontal comparison should preserve the analogous shared-X relationship."""

    divider = ComparisonDividerState(
        enabled=True,
        orientation=ComparisonOrientation.HORIZONTAL,
        visible_segment=QLineF(0.0, 300.0, 800.0, 300.0),
    )
    base_active = position_zoom_badges(
        QRect(0, 0, 800, 600),
        QPointF(100.0, 100.0),
        divider,
        _badge("125%", width=60.0),
        _badge("83%", width=54.0),
    )
    comparison_active = position_zoom_badges(
        QRect(0, 0, 800, 600),
        QPointF(100.0, 450.0),
        divider,
        _badge("125%", width=60.0),
        _badge("83%", width=54.0),
    )

    assert base_active[0].bounds.topLeft() == QPointF(112.0, 112.0)
    assert base_active[1].bounds.top() == 306.0
    assert base_active[0].bounds.left() == base_active[1].bounds.left()
    assert comparison_active[0].bounds.bottom() == 294.0
    assert comparison_active[1].bounds.topLeft() == QPointF(112.0, 462.0)
    assert comparison_active[0].bounds.left() == comparison_active[1].bounds.left()


def test_compare_badges_remain_inside_regions_near_edges_and_divider() -> None:
    """Cursor proximity should never push either badge across its visible region."""

    badges = position_zoom_badges(
        QRect(0, 0, 800, 600),
        QPointF(399.0, 590.0),
        _vertical_divider(),
        _badge("125%", width=80.0),
        _badge("83%", width=70.0),
    )

    assert len(badges) == 2
    assert badges[0].bounds.right() <= 394.0
    assert badges[1].bounds.left() >= 406.0
    assert badges[0].bounds.top() == badges[1].bounds.top()
    assert all(badge.bounds.bottom() <= 596.0 for badge in badges)


def test_offscreen_divider_keeps_visible_base_cursor_badge() -> None:
    """An offscreen comparison side should not suppress the visible base badge."""

    divider = ComparisonDividerState(
        enabled=True,
        orientation=ComparisonOrientation.VERTICAL,
        full_segment=QLineF(900.0, 0.0, 900.0, 600.0),
        visible_segment=None,
    )

    badges = position_zoom_badges(
        QRect(0, 0, 800, 600),
        QPointF(300.0, 200.0),
        divider,
        _badge("125%", width=60.0),
        _badge("83%", width=54.0),
    )

    assert [badge.text for badge in badges] == ["125%"]
    assert badges[0].bounds.topLeft() == QPointF(312.0, 212.0)


def test_offscreen_divider_keeps_visible_comparison_cursor_badge() -> None:
    """An offscreen base side should not suppress the visible comparison badge."""

    divider = ComparisonDividerState(
        enabled=True,
        orientation=ComparisonOrientation.VERTICAL,
        full_segment=QLineF(-100.0, 0.0, -100.0, 600.0),
        visible_segment=None,
    )

    badges = position_zoom_badges(
        QRect(0, 0, 800, 600),
        QPointF(300.0, 200.0),
        divider,
        _badge("125%", width=60.0),
        _badge("83%", width=54.0),
    )

    assert [badge.text for badge in badges] == ["83%"]
    assert badges[0].bounds.topLeft() == QPointF(312.0, 212.0)


def test_narrow_inactive_side_does_not_suppress_active_cursor_badge() -> None:
    """A passive side too narrow for its label should leave active feedback visible."""

    divider = ComparisonDividerState(
        enabled=True,
        orientation=ComparisonOrientation.VERTICAL,
        full_segment=QLineF(760.0, 0.0, 760.0, 600.0),
        visible_segment=QLineF(760.0, 0.0, 760.0, 600.0),
    )

    badges = position_zoom_badges(
        QRect(0, 0, 800, 600),
        QPointF(300.0, 200.0),
        divider,
        _badge("125%", width=60.0),
        _badge("83%", width=54.0),
    )

    assert [badge.text for badge in badges] == ["125%"]
    assert badges[0].bounds.topLeft() == QPointF(312.0, 212.0)


def test_compare_overlay_draws_independent_public_layer_scales_at_cursor() -> None:
    """Compare labels should combine public layer scales with gesture-local geometry."""

    _application()
    base_id = uuid4()
    comparison_id = uuid4()
    pane = QPane(features=())
    pane.resize(800, 600)
    pane.setImagesByID(
        QPane.imageMapFromLists(
            (
                QImage(100, 100, QImage.Format.Format_RGB32),
                QImage(200, 100, QImage.Format.Format_RGB32),
            ),
            ids=(base_id, comparison_id),
        ),
        base_id,
    )
    pane.setComparisonImageID(comparison_id)
    indicator = CanvasZoomIndicator(pane)
    original_divider_state = pane.comparisonDividerState
    pane.comparisonDividerState = _vertical_divider
    try:
        _arm_wheel(indicator, pane, QPointF(120.0, 180.0))
        pane.zoomChanged.emit(1.25)
        painter = _RecordingPainter()
        indicator.draw(painter, _overlay_state())  # type: ignore[arg-type]
    finally:
        pane.comparisonDividerState = original_divider_state
        indicator.close()
        pane.close()

    assert painter.texts == ["200% × 100%", "100%"]
    assert painter.rounded_bounds[0].topLeft() == QPointF(132.0, 192.0)
    assert painter.rounded_bounds[1].left() == 406.0
    assert painter.rounded_bounds[1].top() == 192.0


def test_real_qpane_wheel_zoom_shows_and_paints_indicator() -> None:
    """A real QPane wheel gesture should drive public zoom and overlay APIs."""

    application = _application()
    image_id = uuid4()
    image = QImage(320, 240, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.red)
    pane = QPane(config=Config(smooth_zoom_enabled=False), features=())
    pane.resize(640, 480)
    pane.setImagesByID(QPane.imageMapFromLists((image,), ids=(image_id,)), image_id)
    indicator = CanvasZoomIndicator(pane)
    pane.show()
    application.processEvents()
    pane.setZoom1To1()
    application.processEvents()
    initial_zoom = pane.currentZoom()
    event = _wheel_event(pane, QPointF(300.0, 220.0))
    try:
        indicator.eventFilter(pane, event)
        pane.wheelEvent(event)
        application.processEvents()

        assert pane.currentZoom() > initial_zoom
        assert indicator.opacity == 1.0
        QTest.mouseMove(pane, QPoint(420, 300))
        application.processEvents()
        painter = _RecordingPainter()
        indicator.draw(painter, _overlay_state())  # type: ignore[arg-type]
        assert painter.rounded_bounds[0].topLeft() == QPointF(432.0, 312.0)
        assert pane.grab().size() == QSize(640, 480)
    finally:
        indicator.close()
        pane.close()


def test_visible_indicator_tracks_live_mouse_movement_after_zoom() -> None:
    """Ordinary mouse movement should reposition visible feedback without another zoom."""

    _application()
    pane = QPane(features=())
    indicator = CanvasZoomIndicator(pane)
    _arm_wheel(indicator, pane, QPointF(100.0, 100.0))
    pane.zoomChanged.emit(1.25)
    QApplication.sendEvent(pane, _mouse_move_event(pane, QPointF(240.0, 260.0)))
    painter = _RecordingPainter()
    try:
        indicator.draw(painter, _overlay_state())  # type: ignore[arg-type]
    finally:
        indicator.close()
        pane.close()

    assert painter.rounded_bounds[0].topLeft() == QPointF(252.0, 272.0)


def test_undocked_indicator_uses_same_cursor_geometry_as_docked_canvas() -> None:
    """Floating hosts should not introduce titlebar-specific placement policy."""

    application = _application()
    pane = QPane(features=())
    window = FloatingCanvasWindow(
        pane,
        "Output",
        lambda *_args: None,
        backdrop_mode=None,
    )
    window.resize(800, 600)
    indicator = CanvasZoomIndicator(pane)
    window.show()
    application.processEvents()
    _arm_wheel(indicator, pane, QPointF(300.0, 200.0))
    pane.zoomChanged.emit(1.25)
    QApplication.sendEvent(pane, _mouse_move_event(pane, QPointF(420.0, 280.0)))
    painter = _RecordingPainter()
    try:
        indicator.draw(painter, _overlay_state())  # type: ignore[arg-type]
        rendered = window.grab()
    finally:
        indicator.close()
        window.close()

    assert painter.rounded_bounds[0].topLeft() == QPointF(432.0, 292.0)
    assert rendered.size() == QSize(800, 600)


def test_new_zoom_restores_full_opacity_and_restarts_fade() -> None:
    """Each new gesture should restore visibility before beginning a fresh fade."""

    _application()
    pane = QPane(features=())
    indicator = CanvasZoomIndicator(pane)
    try:
        _arm_wheel(indicator, pane, QPointF(100.0, 100.0))
        pane.zoomChanged.emit(1.25)
        assert _wait_until(lambda: indicator.opacity < 1.0)

        _arm_wheel(indicator, pane, QPointF(120.0, 120.0))
        pane.zoomChanged.emit(1.5)
        assert indicator.opacity == 1.0

        assert _wait_until(lambda: indicator.opacity < 1.0)
        assert _wait_until(lambda: indicator.opacity == 0.0)
    finally:
        indicator.close()
        pane.close()


def test_indicator_uses_output_navigation_surface_material() -> None:
    """Zoom feedback should use the same fill and border tokens as Output navigation."""

    _application()
    pane = QPane(features=())
    indicator = CanvasZoomIndicator(pane)
    _arm_wheel(indicator, pane, QPointF(100.0, 100.0))
    pane.zoomChanged.emit(1.25)
    painter = _RecordingPainter()
    try:
        indicator.draw(painter, _overlay_state())  # type: ignore[arg-type]
    finally:
        indicator.close()
        pane.close()

    assert painter.brushes == [floating_surface_color()]
    assert painter.pens[0].color() == floating_surface_border_color()
    assert painter.text_colors == [floating_surface_text_color()]


def _badge(text: str, *, width: float) -> CanvasZoomBadge:
    """Return a deterministic origin-relative badge for geometry tests."""

    return CanvasZoomBadge(text, QRectF(0.0, 0.0, width, 28.0))


def _vertical_divider() -> ComparisonDividerState:
    """Return a centered vertical comparison divider."""

    return ComparisonDividerState(
        enabled=True,
        orientation=ComparisonOrientation.VERTICAL,
        visible_segment=QLineF(400.0, 0.0, 400.0, 600.0),
    )


def _arm_wheel(
    indicator: CanvasZoomIndicator,
    pane: QPane,
    position: QPointF,
) -> None:
    """Present one positioned wheel event directly to the indicator filter."""

    indicator.eventFilter(pane, _wheel_event(pane, position))


def _wheel_event(pane: QPane, position: QPointF) -> QWheelEvent:
    """Return a local wheel event at a deterministic pane position."""

    global_position = QPointF(pane.mapToGlobal(position.toPoint()))
    return QWheelEvent(
        position,
        global_position,
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def _mouse_move_event(pane: QPane, position: QPointF) -> QMouseEvent:
    """Return a buttonless local mouse-move event for live-tracking tests."""

    global_position = QPointF(pane.mapToGlobal(position.toPoint()))
    return QMouseEvent(
        QEvent.Type.MouseMove,
        position,
        global_position,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _overlay_state() -> OverlayState:
    """Return a public overlay snapshot with deterministic rendered bounds."""

    source_image = QImage(100, 100, QImage.Format.Format_RGB32)
    transform = QTransform()
    transform.scale(2.0, 1.0)
    return OverlayState(
        zoom=1.25,
        qpane_rect=QRect(0, 0, 800, 600),
        source_image=source_image,
        transform=transform,
        current_pan=QPointF(0.0, 0.0),
        physical_viewport_rect=QRectF(0.0, 0.0, 800.0, 600.0),
    )


class _RecordingPainter:
    """Record text and geometry emitted by the zoom overlay."""

    def __init__(self) -> None:
        """Initialize painter state and recorded values."""

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
        """Return current recorded opacity."""

        return self._opacity

    def setOpacity(self, opacity: float) -> None:  # noqa: N802
        """Record painter opacity."""

        self._opacity = opacity

    def setRenderHint(self, *_args: object) -> None:  # noqa: N802
        """Accept render-hint updates."""

    def setFont(self, *_args: object) -> None:  # noqa: N802
        """Accept font updates."""

    def setBrush(self, brush: QColor) -> None:  # noqa: N802
        """Record an assigned fill color."""

        self.brushes.append(QColor(brush))

    def setPen(self, pen: object) -> None:  # noqa: N802
        """Record assigned QPen values while accepting text colors."""

        if isinstance(pen, QPen):
            self.pens.append(QPen(pen))
        elif isinstance(pen, QColor):
            self.text_colors.append(QColor(pen))

    def drawRoundedRect(self, bounds: QRectF, *_args: object) -> None:  # noqa: N802
        """Record rounded badge bounds."""

        self.rounded_bounds.append(QRectF(bounds))

    def drawText(self, _bounds: object, _alignment: object, text: str) -> None:  # noqa: N802
        """Record one centered zoom label."""

        self.texts.append(text)


def _application() -> QApplication:
    """Return the process Qt application required by QWidget tests."""

    instance = QApplication.instance()
    return cast(QApplication, instance) if instance is not None else QApplication([])


def _wait_until(predicate: Callable[[], bool], *, timeout_ms: int = 1_500) -> bool:
    """Process Qt work until an observable condition holds or the timeout expires."""

    timer = QElapsedTimer()
    timer.start()
    while not predicate() and timer.elapsed() < timeout_ms:
        QTest.qWait(10)
        QApplication.processEvents()
    return predicate()
