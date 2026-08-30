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

"""Verify full-window modal ownership against the production shell frame."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QMouseEvent, QResizeEvent
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget
from _pytest.monkeypatch import MonkeyPatch
from shiboken6 import delete, isValid

from substitute.presentation.dialogs.full_window_modal import (
    FullWindowModalBase,
    resolve_full_window_modal_owner,
)
import substitute.presentation.dialogs.full_window_modal_titlebar_bridge as titlebar_bridge_module
from substitute.presentation.shell.window_frame import SubstituteWindowFrame


def _app() -> QApplication:
    """Return the process QApplication for native modal tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_full_window_modal_resolves_outer_shell_before_qfluent_construction() -> None:
    """A body-owned modal should cover the shell title bar and body."""

    app = _app()
    frame = SubstituteWindowFrame(backdrop_mode=None)
    frame.resize(900, 640)
    body = QWidget(frame)
    frame.add_body_widget(body)
    body_layout = QVBoxLayout(body)
    body_layout.addWidget(QPushButton("Body action", body))
    dialog = FullWindowModalBase(body)
    app.processEvents()

    assert dialog.parentWidget() is frame
    assert dialog.geometry().size() == frame.size()
    assert dialog.windowMask.geometry() == dialog.rect()
    titlebar_point = frame.titleBar.mapTo(frame, QPoint(20, 10))
    assert dialog.geometry().contains(titlebar_point)


def test_full_window_modal_tracks_shell_resize_without_showing_a_window() -> None:
    """The hidden mask should remain frame-sized as its owner is resized."""

    app = _app()
    frame = SubstituteWindowFrame(backdrop_mode=None)
    body = QWidget(frame)
    frame.add_body_widget(body)
    frame.resize(760, 520)
    dialog = FullWindowModalBase(body)
    app.processEvents()
    frame.resize(QSize(1024, 720))
    app.sendEvent(frame, QResizeEvent(QSize(1024, 720), QSize(760, 520)))
    app.sendEvent(frame, QEvent(QEvent.Type.LayoutRequest))
    app.processEvents()

    assert dialog.size() == QSize(1024, 720)
    assert dialog.windowMask.size() == QSize(1024, 720)
    assert not dialog.isVisible()


def test_full_window_modal_wash_forwards_only_qualified_titlebar_drag(
    monkeypatch: MonkeyPatch,
) -> None:
    """The wash should preserve native movement without exposing titlebar controls."""

    app = _app()
    frame = SubstituteWindowFrame(backdrop_mode=None)
    frame.resize(900, 640)
    frame.titleBar.resize(frame.width(), frame.titleBar.height())
    titlebar_layout = frame.titleBar.layout()
    if titlebar_layout is not None:
        titlebar_layout.activate()
    body = QWidget(frame)
    frame.add_body_widget(body)
    dialog = FullWindowModalBase(body)
    app.processEvents()
    native_moves: list[tuple[QWidget, QPoint]] = []
    monkeypatch.setattr(
        titlebar_bridge_module,
        "startSystemMove",
        lambda owner, position: native_moves.append((owner, position)),
    )

    titlebar_origin = frame.titleBar.mapTo(frame, QPoint(240, 10))
    wash_origin = dialog.windowMask.mapFrom(frame, titlebar_origin)
    drag_distance = QApplication.startDragDistance() + 1
    wash_destination = wash_origin + QPoint(drag_distance, 0)
    press = _mouse_event(
        QEvent.Type.MouseButtonPress,
        wash_origin,
        button=Qt.MouseButton.LeftButton,
        buttons=Qt.MouseButton.LeftButton,
    )
    move = _mouse_event(
        QEvent.Type.MouseMove,
        wash_destination,
        button=Qt.MouseButton.NoButton,
        buttons=Qt.MouseButton.LeftButton,
    )

    app.sendEvent(dialog.windowMask, press)
    app.sendEvent(dialog.windowMask, move)

    assert native_moves == [(frame, wash_destination)]


def test_full_window_modal_wash_blocks_titlebar_button_clicks() -> None:
    """Covered titlebar buttons should not receive pointer activation."""

    app = _app()
    frame = SubstituteWindowFrame(backdrop_mode=None)
    frame.resize(900, 640)
    frame.titleBar.resize(frame.width(), frame.titleBar.height())
    titlebar_layout = frame.titleBar.layout()
    if titlebar_layout is not None:
        titlebar_layout.activate()
    dialog = FullWindowModalBase(frame)
    app.processEvents()
    minimize_clicks: list[bool] = []
    frame.titleBar.minBtn.clicked.connect(lambda: minimize_clicks.append(True))
    button_center = frame.titleBar.minBtn.mapTo(
        frame,
        frame.titleBar.minBtn.rect().center(),
    )
    wash_position = dialog.windowMask.mapFrom(frame, button_center)

    app.sendEvent(
        dialog.windowMask,
        _mouse_event(
            QEvent.Type.MouseButtonPress,
            wash_position,
            button=Qt.MouseButton.LeftButton,
            buttons=Qt.MouseButton.LeftButton,
        ),
    )
    app.sendEvent(
        dialog.windowMask,
        _mouse_event(
            QEvent.Type.MouseButtonRelease,
            wash_position,
            button=Qt.MouseButton.LeftButton,
            buttons=Qt.MouseButton.NoButton,
        ),
    )

    assert minimize_clicks == []


def test_full_window_modal_replaces_a_destroyed_fallback_owner() -> None:
    """Resolve a fresh owner when the cached startup fallback is destroyed."""

    app = _app()
    app.closeAllWindows()
    app.processEvents()
    stale_owner = resolve_full_window_modal_owner(None)
    delete(stale_owner)

    replacement = resolve_full_window_modal_owner(None)

    assert isValid(stale_owner) is False
    assert isValid(replacement) is True
    assert replacement is not stale_owner


def _mouse_event(
    event_type: QEvent.Type,
    position: QPoint,
    *,
    button: Qt.MouseButton,
    buttons: Qt.MouseButton,
) -> QMouseEvent:
    """Build one deterministic local/global mouse event without showing a window."""

    point = QPointF(position)
    return QMouseEvent(
        event_type,
        point,
        point,
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
