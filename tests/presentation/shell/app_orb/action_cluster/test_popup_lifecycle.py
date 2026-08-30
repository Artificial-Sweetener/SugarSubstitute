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

"""Test app-orb override-popup lifecycle."""

from __future__ import annotations


from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget
import pytest
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]

from substitute.presentation.shell.app_orb_action_cluster import (
    AppOrbActionCluster,
)

from tests.presentation.shell.app_orb.support import app
from tests.presentation.shell.app_orb.action_cluster.support import (
    _MenuProbe,
    _QFluentMenuProbe,
    _WidgetMenuProbe,
    _emit_about_to_hide_during_left_press,
    _send_left_click,
    _send_left_press,
    _send_left_release,
)
from tests.support.qt.lifecycle import activate_widget_layouts


def test_app_orb_override_button_opens_attached_menu() -> None:
    """The custom override button should preserve menu trigger behavior."""

    app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)

    cluster.override_button.click()

    assert len(menu.exec_calls) == 1
    assert cluster.override_button.isChecked() is False
    assert cluster.override_button._menu_controller.is_menu_open() is True
    assert cluster.override_button._background_color().alpha() > 0

    cluster.close()


def test_app_orb_override_button_closes_open_menu_on_second_click() -> None:
    """Clicking the override button again should close its already-open menu."""

    app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)

    cluster.override_button.click()
    cluster.override_button.click()

    assert len(menu.exec_calls) == 1
    assert menu.hide_calls == 1
    assert cluster.override_button.isChecked() is False
    assert cluster.override_button._menu_controller.is_menu_open() is False
    assert cluster.override_button._background_color().alpha() == 0

    cluster.close()


def test_app_orb_override_button_second_mouse_click_consumes_reopen_signal() -> None:
    """Second owner mouse activation should close without emitting a reopen click."""

    app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)
    clicked_states: list[bool] = []
    cluster.override_button.clicked.connect(
        lambda checked: clicked_states.append(bool(checked))
    )
    cluster.show()
    activate_widget_layouts(cluster)

    _send_left_click(cluster.override_button)
    _send_left_click(cluster.override_button)

    assert clicked_states == [False]
    assert len(menu.exec_calls) == 1
    assert menu.hide_calls == 1
    assert cluster.override_button.isChecked() is False
    assert cluster.override_button.isDown() is False
    assert cluster.override_button._menu_controller.is_menu_open() is False
    assert cluster.override_button._menu_controller._suppress_next_owner_click is False
    assert (
        cluster.override_button._menu_controller._application_filter_installed is False
    )

    cluster.close()


def test_app_orb_override_button_popup_grabbed_owner_press_closes_without_reopen() -> (
    None
):
    """A popup-grabbed press over the owner should close without reopening."""

    app()
    cluster = AppOrbActionCluster()
    menu = _WidgetMenuProbe()
    cluster.override_button.setMenu(menu)
    clicked_states: list[bool] = []
    cluster.override_button.clicked.connect(
        lambda checked: clicked_states.append(bool(checked))
    )
    cluster.show()
    activate_widget_layouts(cluster)

    _send_left_click(cluster.override_button)
    owner_center = cluster.override_button.mapToGlobal(
        cluster.override_button.rect().center()
    )
    _send_left_press(menu, owner_center)
    _send_left_release(cluster.override_button, owner_center)

    assert clicked_states == [False]
    assert len(menu.exec_calls) == 1
    assert menu.hide_calls == 1
    assert cluster.override_button._menu_controller.is_menu_open() is False

    cluster.close()


def test_app_orb_override_button_does_not_reopen_after_popup_owner_press(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owner clicks that first auto-hide the popup should not reopen it."""

    app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)
    cluster.show()
    activate_widget_layouts(cluster)

    cluster.override_button.click()
    QCursor.setPos(
        cluster.override_button.mapToGlobal(cluster.override_button.rect().center())
    )
    menu.visible = False
    _emit_about_to_hide_during_left_press(monkeypatch, menu)
    _send_left_click(cluster.override_button)

    assert len(menu.exec_calls) == 1
    assert cluster.override_button.isChecked() is False
    assert cluster.override_button.isDown() is False
    assert cluster.override_button._menu_controller.is_menu_open() is False

    cluster.close()


def test_app_orb_override_button_does_not_reopen_after_system_hide_on_owner() -> None:
    """QFluent system-hide closure over the owner should consume the owner click."""

    app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)
    cluster.show()
    activate_widget_layouts(cluster)

    cluster.override_button.click()
    QCursor.setPos(
        cluster.override_button.mapToGlobal(cluster.override_button.rect().center())
    )
    menu.visible = False
    menu.isHideBySystem = True
    menu.closedSignal.emit()
    _send_left_click(cluster.override_button)

    assert len(menu.exec_calls) == 1
    assert cluster.override_button._menu_controller.is_menu_open() is False

    cluster.close()


def test_app_orb_override_button_owner_suppression_uses_hit_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Popup closure over the cutout should not suppress the next real click."""

    app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)
    cluster.show()
    activate_widget_layouts(cluster)

    cluster.override_button.click()
    QCursor.setPos(cluster.override_button.mapToGlobal(QPoint(0, 0)))
    menu.visible = False
    _emit_about_to_hide_during_left_press(monkeypatch, menu)

    assert cluster.override_button.hitButton(QPoint(0, 0)) is False
    assert cluster.override_button._menu_controller._suppress_next_owner_click is False

    _send_left_click(cluster.override_button)

    assert len(menu.exec_calls) == 2
    assert cluster.override_button.isChecked() is False
    assert cluster.override_button._menu_controller.is_menu_open() is True

    cluster.close()


def test_app_orb_override_button_opens_after_elsewhere_release_clears_owner_ignore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A closing owner gesture delivered elsewhere must not poison later clicks."""

    app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)
    cluster.show()
    activate_widget_layouts(cluster)

    cluster.override_button.click()
    QCursor.setPos(
        cluster.override_button.mapToGlobal(cluster.override_button.rect().center())
    )
    menu.visible = False
    _emit_about_to_hide_during_left_press(monkeypatch, menu)
    other_widget = QWidget()
    other_widget.resize(20, 20)
    other_widget.show()
    activate_widget_layouts(other_widget)
    _send_left_release(other_widget)
    _send_left_click(cluster.override_button)

    assert len(menu.exec_calls) == 2
    assert cluster.override_button.isChecked() is False
    assert cluster.override_button._menu_controller.is_menu_open() is True
    assert cluster.override_button._menu_controller._suppress_next_owner_click is False
    assert (
        cluster.override_button._menu_controller._application_filter_installed is True
    )

    other_widget.close()
    cluster.close()


def test_app_orb_override_button_failed_open_stays_unclicked_visual() -> None:
    """A failed menu open should not leave the override button looking clicked."""

    app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe(open_on_exec=False)
    cluster.override_button.setMenu(menu)

    cluster.override_button.click()

    assert len(menu.exec_calls) == 1
    assert cluster.override_button._menu_controller.is_menu_open() is False
    assert cluster.override_button._background_color().alpha() == 0

    cluster.override_button.click()

    assert len(menu.exec_calls) == 2

    cluster.close()


def test_app_orb_override_button_external_close_repaints_unclicked_visual() -> None:
    """Click-away popup closure should immediately clear the clicked visual."""

    app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)

    cluster.override_button.click()

    assert cluster.override_button._menu_controller.is_menu_open() is True
    assert cluster.override_button._background_color().alpha() > 0

    menu.visible = False
    menu.closedSignal.emit()

    assert cluster.override_button._menu_controller.is_menu_open() is False
    assert cluster.override_button._background_color().alpha() == 0

    cluster.close()


def test_app_orb_override_button_positions_menu_left_anchored() -> None:
    """Shell menus should open from the button's left edge and extend rightward."""

    app()
    cluster = AppOrbActionCluster()
    menu = _QFluentMenuProbe(left_margin=7)
    cluster.override_button.setMenu(menu)
    cluster.show()
    activate_widget_layouts(cluster)

    cluster.override_button.click()

    expected_position = cluster.override_button.mapToGlobal(
        QPoint(0, cluster.override_button.height())
    )
    assert menu.exec_calls[0][0][0] == expected_position
    assert menu.exec_calls[0][1]["aniType"] is MenuAnimationType.DROP_DOWN
    assert menu.view.adjust_calls[-1] == (
        expected_position,
        MenuAnimationType.DROP_DOWN,
    )

    cluster.close()
