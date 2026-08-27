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

"""Test app-orb menu popup lifecycle."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor, QImage
from PySide6.QtWidgets import QWidget
import pytest
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]

from substitute.presentation.shell.app_orb_menu import (
    APP_ORB_MENU_OVERLAP_PX,
    AppOrbMenuButton,
)
from substitute.presentation.shell.chrome_style import APP_ORB_DIAMETER

from tests.presentation.shell.app_orb.support import app
from tests.presentation.shell.app_orb.menu.support import (
    _MenuProbe,
    _QFluentMenuProbe,
    _RendererProbe,
    _emit_about_to_hide_during_left_press,
    _send_left_click,
    _send_left_release,
)
from tests.support.qt.lifecycle import activate_widget_layouts


def test_app_orb_menu_button_closes_open_menu_on_second_click() -> None:
    """Clicking the app orb again should close its already-open command menu."""

    app()
    button = AppOrbMenuButton()
    menu = _MenuProbe()
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)

    button.click()
    button.click()

    assert len(menu.exec_calls) == 1
    assert menu.hide_calls == 1
    assert button.isChecked() is False
    assert button._menu_controller.is_menu_open() is False

    button.close()


def test_app_orb_menu_button_second_mouse_click_consumes_reopen_signal() -> None:
    """Second owner mouse activation should close without emitting a reopen click."""

    app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    menu = _MenuProbe()
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    clicked_states: list[bool] = []
    button.clicked.connect(lambda checked: clicked_states.append(bool(checked)))
    button.show()
    activate_widget_layouts(button)

    _send_left_click(button)
    _send_left_click(button)

    assert clicked_states == [False]
    assert len(menu.exec_calls) == 1
    assert menu.hide_calls == 1
    assert button.isChecked() is False
    assert button.isDown() is False
    assert button._menu_controller.is_menu_open() is False
    assert button._menu_controller._suppress_next_owner_click is False
    assert button._menu_controller._application_filter_installed is False

    button.close()


def test_app_orb_menu_button_does_not_reopen_after_popup_owner_press(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owner clicks that first auto-hide the popup should not reopen it."""

    app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    menu = _MenuProbe()
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    button.show()
    activate_widget_layouts(button)

    button.click()
    QCursor.setPos(button.mapToGlobal(button.rect().center()))
    menu.visible = False
    _emit_about_to_hide_during_left_press(monkeypatch, menu)
    _send_left_click(button)

    assert len(menu.exec_calls) == 1
    assert button.isChecked() is False
    assert button.isDown() is False
    assert button._menu_controller.is_menu_open() is False

    button.close()


def test_app_orb_menu_button_does_not_reopen_after_system_hide_on_owner() -> None:
    """QFluent system-hide closure over the orb should consume the owner click."""

    app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    menu = _MenuProbe()
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    button.show()
    activate_widget_layouts(button)

    button.click()
    QCursor.setPos(button.mapToGlobal(button.rect().center()))
    menu.visible = False
    menu.isHideBySystem = True
    menu.closedSignal.emit()
    _send_left_click(button)

    assert len(menu.exec_calls) == 1
    assert button._menu_controller.is_menu_open() is False

    button.close()


def test_app_orb_menu_button_opens_after_elsewhere_release_clears_owner_ignore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A closing owner gesture delivered elsewhere must not poison later clicks."""

    app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    menu = _MenuProbe()
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    button.show()
    activate_widget_layouts(button)

    button.click()
    QCursor.setPos(button.mapToGlobal(button.rect().center()))
    menu.visible = False
    _emit_about_to_hide_during_left_press(monkeypatch, menu)
    other_widget = QWidget()
    other_widget.resize(20, 20)
    other_widget.show()
    activate_widget_layouts(other_widget)
    _send_left_release(other_widget)
    _send_left_click(button)

    assert len(menu.exec_calls) == 2
    assert button.isChecked() is False
    assert button._menu_controller.is_menu_open() is True
    assert button._menu_controller._suppress_next_owner_click is False
    assert button._menu_controller._application_filter_installed is True

    other_widget.close()
    button.close()


def test_app_orb_menu_button_failed_open_stays_unclicked_visual() -> None:
    """A failed menu open should not leave the orb in its clicked visual state."""

    app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    renderer = _RendererProbe()
    menu = _MenuProbe(open_on_exec=False)
    cast(Any, button)._orb_renderer = renderer
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    image = QImage(
        button.size(),
        QImage.Format.Format_ARGB32,
    )

    button.click()
    button.render(image)

    assert len(menu.exec_calls) == 1
    assert button._menu_controller.is_menu_open() is False
    assert renderer.calls[-1]["pressed"] is False

    button.click()

    assert len(menu.exec_calls) == 2

    button.close()


def test_app_orb_menu_button_external_close_repaints_unclicked_visual() -> None:
    """Click-away popup closure should immediately clear the orb clicked visual."""

    app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    renderer = _RendererProbe()
    menu = _MenuProbe()
    cast(Any, button)._orb_renderer = renderer
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    image = QImage(
        button.size(),
        QImage.Format.Format_ARGB32,
    )

    button.click()
    button.render(image)

    assert button._menu_controller.is_menu_open() is True
    assert renderer.calls[-1]["pressed"] is True

    menu.visible = False
    menu.closedSignal.emit()
    button.render(image)

    assert button._menu_controller.is_menu_open() is False
    assert renderer.calls[-1]["pressed"] is False

    button.close()


def test_app_orb_menu_button_qfluent_menu_tucks_under_orb_edge() -> None:
    """The app-orb menu should overlap the orb edge without covering row text."""

    app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    menu = _QFluentMenuProbe()
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    button.show()
    activate_widget_layouts(button)

    button.click()

    expected_position = button.mapToGlobal(
        QPoint(0, button.height() - APP_ORB_MENU_OVERLAP_PX)
    )
    assert menu.exec_calls[0][0][0] == expected_position
    assert menu.exec_calls[0][1]["aniType"] is MenuAnimationType.DROP_DOWN
    assert menu.view.adjust_calls[-1] == (
        expected_position,
        MenuAnimationType.DROP_DOWN,
    )

    button.close()
