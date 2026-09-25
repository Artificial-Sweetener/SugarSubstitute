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

"""Verify bounded cursor-centered video viewport transformations."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.canvas.output.video_playback_controller import (
    VideoViewportMode,
    VideoViewportState,
)
from substitute.presentation.canvas.output.video_viewport_interaction import (
    VideoViewportInteraction,
    panned_viewport,
    zoomed_viewport,
)
from tests.support.qt.lifecycle import ensure_qt_application


def test_zoom_anchors_cursor_and_reset_scale_prevents_pan() -> None:
    """Zoom should retain the cursor point and fitted video should remain centered."""

    ensure_qt_application()
    surface = QWidget()
    surface.resize(400, 200)

    zoomed = zoomed_viewport(
        VideoViewportState(),
        steps=2.0,
        cursor=QPointF(300.0, 50.0),
        surface=surface,
    )
    fitted_pan = panned_viewport(
        VideoViewportState(),
        delta=QPointF(100.0, 100.0),
        surface=surface,
    )

    assert zoomed.zoom > 1.0
    assert zoomed.zoom == 1.5625
    assert zoomed.pan_x < 0.0
    assert zoomed.pan_y > 0.0
    anchor_x = 0.5
    anchor_y = -0.5
    assert (anchor_x - zoomed.pan_x) / zoomed.zoom == anchor_x
    assert (anchor_y - zoomed.pan_y) / zoomed.zoom == anchor_y
    assert fitted_pan == VideoViewportState()


def test_pan_is_bounded_by_visible_scaled_extent() -> None:
    """Pointer drags should never move scaled video fully outside the viewport."""

    ensure_qt_application()
    surface = QWidget()
    surface.resize(100, 100)

    panned = panned_viewport(
        VideoViewportState(zoom=2.0),
        delta=QPointF(1000.0, -1000.0),
        surface=surface,
    )

    assert panned == VideoViewportState(
        zoom=2.0,
        pan_x=0.5,
        pan_y=-0.5,
        mode=VideoViewportMode.CUSTOM,
    )


def test_space_temporarily_owns_anchored_wheel_zoom_and_drag_pan() -> None:
    """Only the held Space pan/zoom tool should consume wheel and drag input."""

    application = ensure_qt_application()
    surface = QWidget()
    surface.resize(400, 200)
    applied: list[VideoViewportState] = []
    interaction = VideoViewportInteraction(
        surface=surface,
        apply_viewport=applied.append,
        show_fit=lambda: None,
        show_actual_size=lambda _position: None,
    )
    wheel = _wheel_event(surface, QPointF(300.0, 50.0))

    QApplication.sendEvent(surface, wheel)
    assert applied == []

    QApplication.sendEvent(surface, _space_event(QEvent.Type.KeyPress))
    QApplication.sendEvent(surface, _wheel_event(surface, QPointF(300.0, 50.0)))
    assert interaction.pan_zoom_active
    assert applied[-1].zoom == 1.25
    assert applied[-1].pan_x == -0.125
    assert applied[-1].pan_y == 0.125
    assert interaction.last_zoom_anchor == QPointF(300.0, 50.0)
    assert surface.cursor().shape() == Qt.CursorShape.OpenHandCursor

    QApplication.sendEvent(
        surface,
        _mouse_event(
            surface,
            QEvent.Type.MouseButtonPress,
            QPointF(200.0, 100.0),
            button=Qt.MouseButton.LeftButton,
            buttons=Qt.MouseButton.LeftButton,
        ),
    )
    QApplication.sendEvent(
        surface,
        _mouse_event(
            surface,
            QEvent.Type.MouseMove,
            QPointF(240.0, 120.0),
            buttons=Qt.MouseButton.LeftButton,
        ),
    )
    assert applied[-1].pan_x > -0.125
    assert applied[-1].pan_y > 0.125
    assert surface.cursor().shape() == Qt.CursorShape.ClosedHandCursor

    QApplication.sendEvent(surface, _space_event(QEvent.Type.KeyRelease))
    assert not interaction.pan_zoom_active
    assert surface.cursor().shape() == Qt.CursorShape.ArrowCursor
    count = len(applied)
    QApplication.sendEvent(surface, _wheel_event(surface, QPointF(200.0, 100.0)))
    application.processEvents()
    assert len(applied) == count


def test_space_double_click_toggles_fit_and_anchored_one_to_one() -> None:
    """Double-click should toggle Fit and 1:1 only in temporary navigation."""

    ensure_qt_application()
    surface = QWidget()
    surface.resize(400, 200)
    fits: list[bool] = []
    actual_positions: list[QPointF] = []
    interaction = VideoViewportInteraction(
        surface=surface,
        apply_viewport=lambda _state: None,
        show_fit=lambda: fits.append(True),
        show_actual_size=actual_positions.append,
    )
    point = QPointF(300.0, 50.0)

    QApplication.sendEvent(surface, _double_click_event(surface, point))
    assert actual_positions == []

    QApplication.sendEvent(surface, _space_event(QEvent.Type.KeyPress))
    QApplication.sendEvent(surface, _double_click_event(surface, point))
    assert actual_positions == [point]

    interaction.set_state(
        VideoViewportState(zoom=2.0, mode=VideoViewportMode.ACTUAL_SIZE)
    )
    QApplication.sendEvent(surface, _double_click_event(surface, point))
    assert fits == [True]

    QApplication.sendEvent(surface, QEvent(QEvent.Type.FocusOut))
    assert not interaction.pan_zoom_active


def _space_event(event_type: QEvent.Type) -> QKeyEvent:
    """Create one non-repeating Space transition."""

    return QKeyEvent(event_type, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)


def _wheel_event(surface: QWidget, position: QPointF) -> QWheelEvent:
    """Create one upward wheel step at a local surface anchor."""

    return QWheelEvent(
        position,
        QPointF(surface.mapToGlobal(position.toPoint())),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def _mouse_event(
    surface: QWidget,
    event_type: QEvent.Type,
    position: QPointF,
    *,
    button: Qt.MouseButton = Qt.MouseButton.NoButton,
    buttons: Qt.MouseButton = Qt.MouseButton.NoButton,
) -> QMouseEvent:
    """Create one positioned mouse event with explicit held-button state."""

    return QMouseEvent(
        event_type,
        position,
        QPointF(surface.mapToGlobal(position.toPoint())),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def _double_click_event(surface: QWidget, position: QPointF) -> QMouseEvent:
    """Create one primary-button double-click at a local anchor."""

    return _mouse_event(
        surface,
        QEvent.Type.MouseButtonDblClick,
        position,
        button=Qt.MouseButton.LeftButton,
        buttons=Qt.MouseButton.LeftButton,
    )
