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

"""Qt tab and cube-stack fixtures."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import cast

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture(autouse=True)
def _retain_qapplication() -> Iterator[QApplication]:
    """Retain the QApplication wrapper throughout each Qt-backed contract."""

    yield _ensure_qapp()


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _clear_gui_stubs() -> None:
    """Remove lightweight stubs so real Qt widgets can import."""
    qtcore = sys.modules.get("PySide6.QtCore")
    if qtcore is not None and not hasattr(qtcore, "QCoreApplication"):
        for name in list(sys.modules):
            if name == "PySide6" or name.startswith("PySide6."):
                sys.modules.pop(name, None)
    qfw = sys.modules.get("qfluentwidgets")
    if qfw is not None and not hasattr(qfw, "MenuAnimationType"):
        for name in list(sys.modules):
            if name == "qfluentwidgets" or name.startswith("qfluentwidgets."):
                sys.modules.pop(name, None)
    qframe = sys.modules.get("qframelesswindow")
    if qframe is not None and not hasattr(qframe, "WindowEffect"):
        for name in list(sys.modules):
            if name == "qframelesswindow" or name.startswith("qframelesswindow."):
                sys.modules.pop(name, None)
    sys.modules.pop("sugarsubstitute_shared.presentation.fluent_tooltips", None)


def _wheel_event(widget: QWidget, *, angle_delta_y: int) -> QWheelEvent:
    """Build one wheel event at the center of a widget."""

    local_point = widget.rect().center()
    return QWheelEvent(
        QPointF(local_point),
        QPointF(widget.mapToGlobal(local_point)),
        QPoint(0, 0),
        QPoint(0, angle_delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
