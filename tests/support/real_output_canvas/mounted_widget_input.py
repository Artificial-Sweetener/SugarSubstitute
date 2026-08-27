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

"""Drive real-shell controls only through reachable mounted mouse targets."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from tests.support.qt.semantic_wait import wait_for_qt_condition


class MountedWidgetInput:
    """Own hit-tested physical input for mounted real-shell fixtures."""

    def __init__(self, application: QApplication) -> None:
        """Bind the Qt application that resolves topmost widgets."""

        self._application = application

    def click(self, widget: QWidget, *, subject: str) -> None:
        """Click a visible widget through the topmost target at its center."""

        wait_for_qt_condition(lambda: self.is_targetable(widget))
        if not widget.isVisible():
            raise AssertionError(
                f"{subject} is not visible: widget={type(widget).__name__}; "
                f"geometry={widget.geometry()}"
            )
        global_position = widget.mapToGlobal(widget.rect().center())
        hit_widget = self._application.widgetAt(global_position)
        if hit_widget is None:
            raise AssertionError(
                f"{subject} has no mouse target: "
                f"widget={type(widget).__name__}; "
                f"global_position={global_position}; "
                f"geometry={widget.geometry()}"
            )
        if hit_widget is not widget and not widget.isAncestorOf(hit_widget):
            raise AssertionError(
                f"{subject} is occluded: widget={type(widget).__name__}; "
                f"hit={type(hit_widget).__name__}; "
                f"global_position={global_position}"
            )
        QTest.mouseClick(
            hit_widget,
            Qt.MouseButton.LeftButton,
            pos=hit_widget.mapFromGlobal(global_position),
        )

    def is_targetable(self, widget: QWidget) -> bool:
        """Return whether a widget's center is reachable through mounted Qt chrome."""

        if not widget.isVisible():
            return False
        global_position = widget.mapToGlobal(widget.rect().center())
        hit_widget = self._application.widgetAt(global_position)
        return hit_widget is widget or (
            hit_widget is not None and widget.isAncestorOf(hit_widget)
        )


__all__ = ["MountedWidgetInput"]
