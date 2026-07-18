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

"""Project route-owned controls into the shared shell chrome."""

from __future__ import annotations

from typing import Any


class ShellChromeController:
    """Own workflow-route visibility and availability in shell chrome."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose route chrome is projected."""

        self._shell = shell

    def set_orb_action_cluster_visible(self, visible: bool) -> None:
        """Show workflow-only under-orb actions for workflow routes."""

        if not visible:
            self._close_override_menu_if_open()

        cluster = getattr(self._shell, "orbActionCluster", None)
        set_visible = getattr(cluster, "setVisible", None)
        if callable(set_visible):
            set_visible(visible)

    def set_settings_toolbar_search_visible(self, visible: bool) -> None:
        """Show Settings search in shell chrome only while Settings is active."""

        search_box = getattr(self._shell, "settingsToolbarSearchBox", None)
        set_visible = getattr(search_box, "setVisible", None)
        if callable(set_visible):
            set_visible(visible)
            return

        show = getattr(search_box, "show", None)
        hide = getattr(search_box, "hide", None)
        if visible and callable(show):
            show()
        elif not visible and callable(hide):
            hide()

    def set_workflow_override_toolbar_visible(self, visible: bool) -> None:
        """Hide workflow override toolbar controls outside workflow routes."""

        if visible:
            return
        manager = getattr(self._shell, "active_override_manager", None)
        clear_controls = getattr(manager, "clear_toolbar_override_controls", None)
        if callable(clear_controls):
            clear_controls()

    def set_app_orb_workflow_file_actions_enabled(self, enabled: bool) -> None:
        """Toggle app-orb workflow file commands for the current shell route."""

        app_orb_menu = getattr(self._shell, "appOrbMenuButton", None)
        set_enabled = getattr(app_orb_menu, "set_workflow_file_actions_enabled", None)
        if callable(set_enabled):
            set_enabled(enabled)

    def _close_override_menu_if_open(self) -> None:
        """Close workflow override chrome before hiding its action cluster."""

        controller = getattr(
            getattr(self._shell, "override_dropdown_btn", None),
            "_menu_controller",
            None,
        )
        close_menu_if_open = getattr(controller, "close_menu_if_open", None)
        if callable(close_menu_if_open):
            close_menu_if_open()
