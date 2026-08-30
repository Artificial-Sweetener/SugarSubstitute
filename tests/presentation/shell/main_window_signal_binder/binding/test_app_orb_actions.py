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

"""Verify app-orb file and runtime action routing."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QFileDialog, QMessageBox
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.presentation.shell.main_window_signal_binder import (
    MainWindowSignalBinder,
)
from substitute.presentation.shell.cube_loader import load_cube_async
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)

from .support import _AppOrbMenu


def test_app_orb_menu_routes_file_actions_and_runtime_requests() -> None:
    """App-orb wiring should inject UI adapters and route runtime actions."""

    menu = _AppOrbMenu()
    enabled_calls: list[bool] = []
    load_calls: list[dict[str, object]] = []
    save_calls: list[str] = []
    save_as_calls: list[dict[str, object]] = []
    export_calls: list[dict[str, object]] = []
    settings_calls: list[str] = []
    comfy_settings_calls: list[str] = []
    gui_restart_calls: list[str] = []
    restart_calls: list[str] = []

    def direct_load(_path: Path) -> str:
        """Return a stable direct-workflow result for signal routing."""

        return "direct"

    def direct_can_load(_path: Path) -> bool:
        """Report direct-workflow support for signal routing."""

        return True

    shell = SimpleNamespace(
        _active_workspace_route=SETTINGS_WORKSPACE_ROUTE,
        shell_chrome_controller=SimpleNamespace(
            set_app_orb_workflow_file_actions_enabled=enabled_calls.append,
        ),
        workspace_controller=SimpleNamespace(
            on_settings_tab_selected=lambda: settings_calls.append("settings"),
        ),
        workspace_file_actions=SimpleNamespace(
            on_load_clicked=lambda **kwargs: load_calls.append(kwargs),
            on_save_clicked=lambda: save_calls.append("save"),
            on_save_as_clicked=lambda **kwargs: save_as_calls.append(kwargs),
            on_export_comfy_workflow_clicked=lambda **kwargs: export_calls.append(
                kwargs
            ),
        ),
        direct_workflow_file_actions=SimpleNamespace(
            load_document=direct_load,
            can_load_document=direct_can_load,
        ),
        comfy_runtime_actions=SimpleNamespace(
            open_comfyui_settings_webview=lambda: comfy_settings_calls.append(
                "comfy_settings"
            ),
            request_comfy_restart=lambda: restart_calls.append("restart"),
        ),
        request_full_gui_reload=lambda: gui_restart_calls.append("gui_restart"),
    )

    MainWindowSignalBinder(shell).attach_app_orb_menu(menu)
    menu.openRequested.fire()
    menu.saveRequested.fire()
    menu.saveAsRequested.fire()
    menu.exportRequested.fire()
    menu.settingsRequested.fire()
    menu.comfyUiSettingsRequested.fire()
    menu.restartGuiRequested.fire()
    menu.restartComfyRequested.fire()

    assert shell.appOrbMenuButton is menu
    assert enabled_calls == [False]
    assert load_calls == [
        {
            "file_dialog": QFileDialog,
            "cube_loader": load_cube_async,
            "icon_provider": FIF,
            "message_box": QMessageBox,
            "load_direct_workflow_document": direct_load,
            "can_load_direct_workflow_document": direct_can_load,
        }
    ]
    assert save_calls == ["save"]
    assert save_as_calls == [{"file_dialog": QFileDialog}]
    assert export_calls == [
        {
            "file_dialog": QFileDialog,
            "message_box": QMessageBox,
        }
    ]
    assert settings_calls == ["settings"]
    assert comfy_settings_calls == ["comfy_settings"]
    assert gui_restart_calls == ["gui_restart"]
    assert restart_calls == ["restart"]
