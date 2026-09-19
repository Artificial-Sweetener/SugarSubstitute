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

"""Verify toggle menu buttons through the real Qt and QFluent owners."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QHideEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton, QWidget
from qfluentwidgets import RoundMenu  # type: ignore[import-untyped]

from substitute.presentation.widgets.menu_button_controller import (
    MenuButtonController,
)
from substitute.presentation.widgets.menu_buttons import (
    ToggleDropDownPushButton,
    TogglePrimarySplitPushButton,
    ToggleSplitToolButton,
    ToggleTransparentDropDownToolButton,
)
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _RecordingRoundMenu(RoundMenu):  # type: ignore[misc]
    """Expose real menu geometry while recording nonblocking open requests."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a parent-owned menu with empty content."""

        super().__init__(parent=parent)
        self.exec_calls = 0
        self.hidden_calls = 0

    def exec(self, *_args: object, **_kwargs: object) -> None:
        """Record and show the menu without an animation clock."""

        self.exec_calls += 1
        self.show()

    def hide(self) -> None:
        """Record explicit toggle hides before delegating to Qt."""

        self.hidden_calls += 1
        super().hide()


class _RecordingPopup(QWidget):
    """Provide the minimal real QWidget boundary accepted by split buttons."""

    closedSignal = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a parent-owned popup with deterministic counters."""

        super().__init__(parent, Qt.WindowType.Tool)
        self.exec_calls = 0
        self.hidden_calls = 0
        self.isHideBySystem = False

    def exec(self, _position: QPoint) -> None:
        """Record and show one split-button popup request."""

        self.exec_calls += 1
        self.show()

    def hide(self) -> None:
        """Record explicit toggle hides before delegating to Qt."""

        self.hidden_calls += 1
        super().hide()

    def hideEvent(self, event: QHideEvent) -> None:
        """Publish the popup lifecycle event used by the production tracker."""

        super().hideEvent(event)
        self.closedSignal.emit()


def test_transparent_dropdown_second_click_closes_and_third_reopens() -> None:
    """Repeated real trigger clicks should alternate the attached menu state."""

    ensure_qt_application()
    button = ToggleTransparentDropDownToolButton()
    menu = _RecordingRoundMenu(button)
    button.set_popup_menu(menu)
    button.show()

    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    wait_for_qt_condition(menu.isVisible)
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    wait_for_qt_condition(lambda: not menu.isVisible())
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    wait_for_qt_condition(menu.isVisible)

    assert menu.exec_calls == 2
    assert menu.hidden_calls == 1
    destroy_qt_object(button)


def test_split_tool_drop_arrow_preserves_signal_and_toggles_flyout() -> None:
    """The real drop arrow should retain its public signal while toggling."""

    ensure_qt_application()
    button = ToggleSplitToolButton()
    popup = _RecordingPopup(button)
    drop_clicks: list[str] = []
    button.dropDownClicked.connect(lambda: drop_clicks.append("drop"))
    button.set_popup_flyout(popup)

    button.dropButton.clicked.emit()
    button.dropButton.clicked.emit()
    button.dropButton.clicked.emit()

    assert drop_clicks == ["drop", "drop", "drop"]
    assert popup.exec_calls == 2
    assert popup.hidden_calls == 1
    destroy_qt_object(button)


def test_primary_split_button_preserves_primary_action() -> None:
    """The real primary child should remain independent of flyout toggling."""

    ensure_qt_application()
    button = TogglePrimarySplitPushButton()
    popup = _RecordingPopup(button)
    primary_clicks: list[str] = []
    button.clicked.connect(lambda: primary_clicks.append("primary"))
    button.set_popup_flyout(popup)

    button.button.clicked.emit()
    button.dropButton.clicked.emit()

    assert primary_clicks == ["primary"]
    assert popup.exec_calls == 1
    destroy_qt_object(button)


def test_dropdown_push_button_uses_the_same_toggle_lifecycle() -> None:
    """Push-button dropdowns should close and reopen through the shared owner."""

    ensure_qt_application()
    button = ToggleDropDownPushButton()
    menu = _RecordingRoundMenu(button)
    button.set_popup_menu(menu)
    button.show()

    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    wait_for_qt_condition(menu.isVisible)
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    wait_for_qt_condition(lambda: not menu.isVisible())
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    wait_for_qt_condition(menu.isVisible)

    assert menu.exec_calls == 2
    assert menu.hidden_calls == 1
    destroy_qt_object(button)


def test_dynamic_menu_factory_builds_only_for_legitimate_opens() -> None:
    """A second button click should close without rebuilding a dynamic menu."""

    ensure_qt_application()
    button = QPushButton()
    menus: list[_RecordingRoundMenu] = []

    def build_menu() -> _RecordingRoundMenu:
        """Build one observable menu for an allowed open request."""

        menu = _RecordingRoundMenu(button)
        menus.append(menu)
        return menu

    controller = MenuButtonController(
        button,
        menu_position=lambda: button.mapToGlobal(QPoint(0, button.height())),
    )
    controller.set_menu_factory(build_menu)

    button.click()
    button.click()
    button.click()

    assert len(menus) == 2
    assert [menu.exec_calls for menu in menus] == [1, 1]
    assert menus[0].hidden_calls == 1
    destroy_qt_object(button)


def test_external_dynamic_menu_close_allows_a_fresh_open() -> None:
    """External closure should reset shared state before the next click."""

    ensure_qt_application()
    button = QPushButton()
    menus: list[_RecordingRoundMenu] = []
    controller = MenuButtonController(
        button,
        menu_position=lambda: QPoint(),
    )

    def build_menu() -> _RecordingRoundMenu:
        """Build and retain one menu for lifecycle assertions."""

        menu = _RecordingRoundMenu(button)
        menus.append(menu)
        return menu

    controller.set_menu_factory(build_menu)

    button.click()
    menus[0].isHideBySystem = False
    menus[0].hide()
    wait_for_qt_condition(lambda: not controller.is_menu_open())
    button.click()

    assert len(menus) == 2
    assert controller.menu() is menus[1]
    destroy_qt_object(button)
