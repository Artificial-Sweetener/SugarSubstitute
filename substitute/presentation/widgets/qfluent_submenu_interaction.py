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

"""Add deterministic click-to-open behavior to rendered QFluent submenus."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QWidget
from qfluentwidgets import RoundMenu  # type: ignore[import-untyped]


def install_submenu_click_openers(menu: RoundMenu) -> None:
    """Install click-to-open behavior throughout one rendered menu tree."""

    for submenu in getattr(menu, "_subMenus", ()):
        if isinstance(submenu, RoundMenu):
            _install_submenu_click_opener(menu, submenu)
            install_submenu_click_openers(submenu)


def _install_submenu_click_opener(
    parent_menu: RoundMenu,
    submenu: RoundMenu,
) -> None:
    """Install one opener on a rendered QFluent submenu row."""

    item = getattr(submenu, "menuItem", None)
    view = getattr(parent_menu, "view", None)
    if item is None or view is None:
        return
    item_widget = getattr(view, "itemWidget", None)
    if not callable(item_widget):
        return
    widget = item_widget(item)
    if not isinstance(widget, QWidget):
        return

    opener = QFluentSubmenuClickOpener(parent_menu, submenu, parent_menu)
    widget.installEventFilter(opener)
    openers = getattr(parent_menu, "_substitute_submenu_click_openers", None)
    if not isinstance(openers, list):
        openers = []
        setattr(parent_menu, "_substitute_submenu_click_openers", openers)
    openers.append(opener)


class QFluentSubmenuClickOpener(QObject):
    """Open a QFluent submenu when its row is clicked."""

    def __init__(
        self,
        parent_menu: object,
        submenu: object,
        parent: QObject,
    ) -> None:
        """Store the parent and submenu interaction targets."""

        super().__init__(parent)
        self._parent_menu = parent_menu
        self._submenu = submenu

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Consume submenu row clicks and open the child menu."""

        if event.type() == QEvent.Type.MouseButtonPress:
            QTimer.singleShot(0, self._open_submenu)
            return True
        if event.type() == QEvent.Type.MouseButtonRelease:
            return True
        return super().eventFilter(watched, event)

    def _open_submenu(self) -> None:
        """Open the submenu through QFluent's placement calculation."""

        item = getattr(self._submenu, "menuItem", None)
        if item is None:
            return
        setattr(self._parent_menu, "lastHoverItem", item)
        setattr(self._parent_menu, "lastHoverSubMenuItem", item)
        timer = getattr(self._parent_menu, "timer", None)
        stop = getattr(timer, "stop", None)
        if callable(stop):
            stop()
        open_timeout = getattr(self._parent_menu, "_onShowMenuTimeOut", None)
        if callable(open_timeout):
            open_timeout()


__all__ = ["QFluentSubmenuClickOpener", "install_submenu_click_openers"]
