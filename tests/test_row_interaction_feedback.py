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

"""Tests for shared row interaction feedback behavior."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from substitute.presentation.widgets.row_interaction_feedback import (
    RowInteractionFeedback,
)


class _MouseEvent:
    """Small mouse event stand-in for direct helper tests."""

    def __init__(self, event_type: QEvent.Type, point: QPoint) -> None:
        """Store event type and position."""

        self._event_type = event_type
        self._point = point
        self.accepted = False

    def type(self) -> QEvent.Type:
        """Return the stored event type."""

        return self._event_type

    def button(self) -> Qt.MouseButton:
        """Return the left mouse button."""

        return Qt.MouseButton.LeftButton

    def position(self) -> object:
        """Return a QPoint-like object with Qt 6's toPoint method."""

        point = self._point

        class _Position:
            """Expose the point through the Qt mouse-event API."""

            def toPoint(self) -> QPoint:
                return point

        return _Position()

    def accept(self) -> None:
        """Record event acceptance."""

        self.accepted = True


def test_row_interaction_feedback_activates_owner_clicks() -> None:
    """Enabled feedback should invoke activation for an inside owner click."""

    _app()
    owner = QWidget()
    owner.resize(40, 24)
    activations: list[str] = []
    feedback = RowInteractionFeedback(
        owner,
        overlay_path=_rounded_path,
        activation=lambda: activations.append("activated"),
        animate=False,
    )

    assert feedback.has_activation() is True
    assert feedback.is_feedback_enabled() is True

    assert feedback.handle_mouse_press(
        _MouseEvent(QEvent.Type.MouseButtonPress, QPoint(4, 4))
    )
    assert feedback.current_overlay_color().alpha() == 0x33
    assert feedback.handle_mouse_release(
        _MouseEvent(QEvent.Type.MouseButtonRelease, QPoint(4, 4))
    )

    assert activations == ["activated"]
    assert feedback.current_overlay_color().alpha() == 0
    owner.deleteLater()


def test_row_interaction_feedback_ignores_outside_release_activation() -> None:
    """A press released outside the owner should clear press without activation."""

    _app()
    owner = QWidget()
    owner.resize(20, 20)
    activations: list[str] = []
    feedback = RowInteractionFeedback(
        owner,
        overlay_path=_rounded_path,
        activation=lambda: activations.append("activated"),
        animate=False,
    )

    feedback.handle_mouse_press(_MouseEvent(QEvent.Type.MouseButtonPress, QPoint(2, 2)))
    feedback.handle_mouse_release(
        _MouseEvent(QEvent.Type.MouseButtonRelease, QPoint(30, 30))
    )

    assert activations == []
    assert feedback.current_overlay_color().alpha() == 0
    owner.deleteLater()


def test_row_interaction_feedback_routes_child_target_clicks() -> None:
    """Registered body children should delegate click release to row activation."""

    _app()
    owner = QWidget()
    owner.resize(80, 28)
    child = QLabel(owner)
    child.resize(20, 20)
    activations: list[str] = []
    feedback = RowInteractionFeedback(
        owner,
        overlay_path=_rounded_path,
        activation=lambda: activations.append("activated"),
        animate=False,
    )
    feedback.set_interactive_targets((child,))

    assert feedback.eventFilter(
        child,
        _MouseEvent(QEvent.Type.MouseButtonPress, QPoint(4, 4)),
    )
    assert feedback.eventFilter(
        child,
        _MouseEvent(QEvent.Type.MouseButtonRelease, QPoint(4, 4)),
    )

    assert activations == ["activated"]
    child.deleteLater()
    owner.deleteLater()


def test_row_interaction_feedback_supports_feedback_without_activation() -> None:
    """Feedback-only rows should light up without exposing click activation."""

    _app()
    owner = QWidget()
    owner.resize(40, 24)
    feedback = RowInteractionFeedback(
        owner,
        overlay_path=_rounded_path,
        feedback_enabled=True,
        animate=False,
    )

    feedback.set_hovered(True)
    assert feedback.has_activation() is False
    assert feedback.is_feedback_enabled() is True
    assert feedback.current_overlay_color().alpha() == 0x19

    feedback.set_pressed(True)
    assert feedback.current_overlay_color().alpha() == 0x33
    owner.deleteLater()


def test_row_interaction_feedback_forced_hover_survives_disabled_feedback() -> None:
    """Active rows can retain hover-style overlay without enabling interactions."""

    _app()
    owner = QWidget()
    feedback = RowInteractionFeedback(
        owner,
        overlay_path=_rounded_path,
        animate=False,
    )

    feedback.set_forced_hovered(True)

    assert feedback.is_feedback_enabled() is False
    assert feedback.current_overlay_color().alpha() == 0x19
    owner.deleteLater()


def _rounded_path(rect: QRect) -> QPainterPath:
    """Return a simple rounded path for helper tests."""

    path = QPainterPath()
    path.addRoundedRect(QRectF(rect), 4, 4)
    return path


def _app() -> QApplication:
    """Return an existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
