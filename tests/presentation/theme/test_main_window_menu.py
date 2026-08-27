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

"""Verify theme switching preserves main-window menu action ownership."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from qfluentwidgets import Theme  # type: ignore[import-untyped]

from substitute.presentation.shell.app_orb_action_cluster import (
    APP_ORB_CUBE_STACK_BUTTON_OBJECT_NAME,
    APP_ORB_OVERRIDE_BUTTON_OBJECT_NAME,
)
from substitute.presentation.shell.main_window_menu import build_main_window_menu
from tests.presentation.theme.support import ThemeWidgetOwner


def test_toolbar_keeps_file_actions_in_app_orb(
    theme_owner: ThemeWidgetOwner,
) -> None:
    """Toolbar leaves file actions to the app orb across theme changes."""

    with theme_owner.using_theme(Theme.DARK):
        host = theme_owner.own(QWidget())
        widgets = build_main_window_menu(host, workspace_controller=object())
        host.resize(420, widgets.menu_bar.height())
        host.show()
        theme_owner.wait_until(host.isVisible)

        assert widgets.orb_action_cluster is not None
        assert (
            widgets.cube_stack_mode_button.objectName()
            == APP_ORB_CUBE_STACK_BUTTON_OBJECT_NAME
        )
        assert (
            widgets.override_dropdown_btn.objectName()
            == APP_ORB_OVERRIDE_BUTTON_OBJECT_NAME
        )
        assert not hasattr(widgets, "load_button")
        assert not hasattr(widgets, "save_button")
        assert not hasattr(widgets, "save_as_action")
        assert not hasattr(widgets, "export_action")

        theme_owner.switch_theme(Theme.LIGHT)

        assert (
            widgets.cube_stack_mode_button.objectName()
            == APP_ORB_CUBE_STACK_BUTTON_OBJECT_NAME
        )
        assert (
            widgets.override_dropdown_btn.objectName()
            == APP_ORB_OVERRIDE_BUTTON_OBJECT_NAME
        )
