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

"""Test click-to-open interaction for nested dimension menus."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication

import substitute.presentation.editor.panel.menus.dimension_row_actions as dimension_row_actions
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _TimerDouble:
    """Record submenu timer cancellation."""

    def __init__(self) -> None:
        """Initialize empty stop-call tracking."""

        self.stop_calls = 0

    def stop(self) -> None:
        """Record one stop request."""

        self.stop_calls += 1


class _ClickableMenuDouble(QObject):
    """Record QFluent submenu hover and open state."""

    def __init__(self) -> None:
        """Initialize the menu state observed by the opener."""

        super().__init__()
        self.timer = _TimerDouble()
        self.lastHoverItem: object | None = None
        self.lastHoverSubMenuItem: object | None = None
        self.open_calls = 0

    def _onShowMenuTimeOut(self) -> None:
        """Record immediate opening through QFluent placement logic."""

        self.open_calls += 1


class _SubmenuDouble:
    """Provide the child-menu item identity used by the opener."""

    def __init__(self) -> None:
        """Initialize one menu-item sentinel."""

        self.menuItem = object()


def test_click_is_consumed_and_opens_submenu(
    qt_application_owner: QApplication,
) -> None:
    """Consume submenu row clicks and open the child on the queued Qt turn."""

    _ = qt_application_owner
    parent_menu = _ClickableMenuDouble()
    submenu = _SubmenuDouble()
    opener = dimension_row_actions._SubmenuClickOpener(
        parent_menu,
        submenu,
        parent_menu,
    )
    watched = QObject()
    try:
        assert (
            opener.eventFilter(
                watched,
                QEvent(QEvent.Type.MouseButtonPress),
            )
            is True
        )
        assert (
            opener.eventFilter(
                watched,
                QEvent(QEvent.Type.MouseButtonRelease),
            )
            is True
        )
        wait_for_qt_condition(lambda: parent_menu.open_calls == 1)

        assert parent_menu.timer.stop_calls == 1
        assert parent_menu.lastHoverItem is submenu.menuItem
        assert parent_menu.lastHoverSubMenuItem is submenu.menuItem
    finally:
        destroy_qt_object(watched)
        destroy_qt_object(parent_menu)
