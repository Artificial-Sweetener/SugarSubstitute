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

"""Verify model discovery stays inside its washed owning shell."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from substitute.presentation.model_discovery.discovery_modal import (
    ModelDiscoveryModal,
)
from substitute.presentation.model_discovery.discovery_overlay import (
    ModelDiscoveryOverlay,
)
from substitute.presentation.shell.window_frame import SubstituteWindowFrame
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


def test_discovery_washes_the_shell_without_opening_another_window() -> None:
    """The model gallery must be a centered child over the full outer frame."""

    application = ensure_qt_application()
    frame = SubstituteWindowFrame(backdrop_mode=None)
    frame.resize(1200, 820)
    body = QWidget(frame)
    frame.add_body_widget(body)
    QVBoxLayout(body)
    frame.show()
    application.processEvents()
    existing_windows = set(QApplication.topLevelWidgets())
    overlay = ModelDiscoveryOverlay(owner=body)
    modal = ModelDiscoveryModal(parent=overlay)
    overlay.attach(modal)

    overlay.present()
    modal.show_loading()
    application.processEvents()

    assert overlay.modal_owner is frame
    assert overlay.parentWidget() is frame
    assert overlay.geometry() == frame.rect()
    assert overlay.isVisible()
    assert not overlay.isWindow()
    assert modal.isVisible()
    assert not modal.isWindow()
    assert overlay.rect().contains(modal.geometry())
    assert set(QApplication.topLevelWidgets()) == existing_windows

    modal.reject()
    overlay.hide()
    frame.close()
    destroy_qt_object(frame)


def test_discovery_wash_tracks_shell_resize_and_can_reopen() -> None:
    """A retained gallery must keep its wash bounded to the resized shell."""

    application = ensure_qt_application()
    frame = SubstituteWindowFrame(backdrop_mode=None)
    frame.resize(1180, 800)
    frame.show()
    overlay = ModelDiscoveryOverlay(owner=frame)
    modal = ModelDiscoveryModal(parent=overlay)
    overlay.attach(modal)
    overlay.present()
    modal.show_loading()
    application.processEvents()

    frame.resize(QSize(1360, 900))
    application.processEvents()

    assert overlay.geometry() == frame.rect()
    assert overlay.rect().contains(modal.geometry())
    modal.reject()
    overlay.hide()
    overlay.present()
    modal.show_loading()
    application.processEvents()
    assert overlay.isVisible() and modal.isVisible()
    assert not modal.isWindow()

    modal.reject()
    overlay.hide()
    frame.close()
    destroy_qt_object(frame)
