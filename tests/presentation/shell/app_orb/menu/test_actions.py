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

"""Test app-orb menu commands, localization, and appearance."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QEvent, QPoint, QTranslator
import pytest

import substitute.presentation.resources.app_icon as app_icon_module
from substitute.presentation.shell.app_orb_menu import (
    APP_ORB_MENU_ACCESSIBLE_NAME,
    APP_ORB_MENU_OBJECT_NAME,
    COMFYUI_SETTINGS_MENU_TEXT,
    EXPORT_COMFY_WORKFLOW_MENU_TEXT,
    OPEN_SUGAR_SCRIPT_MENU_TEXT,
    RESTART_COMFYUI_MENU_TEXT,
    RESTART_GUI_MENU_TEXT,
    SAVE_SUGAR_SCRIPT_AS_MENU_TEXT,
    SAVE_SUGAR_SCRIPT_MENU_TEXT,
    SETTINGS_MENU_TEXT,
    AppOrbMenuButton,
)
from substitute.presentation.shell.chrome_style import APP_ORB_DIAMETER

from tests.presentation.shell.app_orb.support import app


def test_app_orb_menu_button_exposes_expected_menu_actions() -> None:
    """The app orb should own the first-pass application command menu."""

    app()
    button = AppOrbMenuButton()

    assert button.objectName() == APP_ORB_MENU_OBJECT_NAME
    assert button.isCheckable() is False
    assert button.toolTip() == APP_ORB_MENU_ACCESSIBLE_NAME
    assert button.accessibleName() == APP_ORB_MENU_ACCESSIBLE_NAME
    assert button._open_action.text() == OPEN_SUGAR_SCRIPT_MENU_TEXT
    assert button._save_action.text() == SAVE_SUGAR_SCRIPT_MENU_TEXT
    assert button._save_as_action.text() == SAVE_SUGAR_SCRIPT_AS_MENU_TEXT
    assert button._export_action.text() == EXPORT_COMFY_WORKFLOW_MENU_TEXT
    assert button._settings_action.text() == SETTINGS_MENU_TEXT
    assert button._comfyui_settings_action.text() == COMFYUI_SETTINGS_MENU_TEXT
    assert button._restart_gui_action.text() == RESTART_GUI_MENU_TEXT
    assert button._restart_comfyui_action.text() == RESTART_COMFYUI_MENU_TEXT
    restart_actions = [
        action.text()
        for action in button._menu.actions()
        if action.text() in {RESTART_GUI_MENU_TEXT, RESTART_COMFYUI_MENU_TEXT}
    ]
    assert restart_actions == [RESTART_GUI_MENU_TEXT, RESTART_COMFYUI_MENU_TEXT]
    assert not hasattr(button, "_reopen_closed_workflow_action")
    assert not hasattr(button, "reopenClosedWorkflowRequested")
    assert not hasattr(button, "set_reopen_closed_workflow_enabled")

    button.close()


def test_app_orb_menu_retranslates_existing_actions_in_place() -> None:
    """The primary application menu must switch language without reconstruction."""

    application = app()
    resource_root = Path(app_icon_module.__file__).resolve().parent / "i18n"
    chinese = QTranslator()
    japanese = QTranslator()
    assert chinese.load(str(resource_root / "sugarsubstitute_zh_CN.qm"))
    assert japanese.load(str(resource_root / "sugarsubstitute_ja_JP.qm"))
    assert application.installTranslator(chinese)
    button = AppOrbMenuButton()
    try:
        assert button.toolTip() == "应用菜单"
        assert button.accessibleName() == "应用菜单"
        assert button._open_action.text() == "打开 Sugar Script..."
        assert button._save_action.text() == "保存 Sugar Script"
        assert button._settings_action.text() == "设置"
        assert button._restart_gui_action.text() == "重启图形界面"

        assert application.removeTranslator(chinese)
        assert application.installTranslator(japanese)
        application.sendEvent(button, QEvent(QEvent.Type.LanguageChange))

        assert button.toolTip() == "アプリケーションメニュー"
        assert button.accessibleName() == "アプリケーションメニュー"
        assert button._open_action.text() == "Sugar Script を開く..."
        assert button._save_action.text() == "Sugar Script を保存"
        assert button._settings_action.text() == "設定"
        assert button._restart_gui_action.text() == "GUI を再起動"
    finally:
        application.removeTranslator(japanese)
        application.removeTranslator(chinese)
        button.close()


def test_app_orb_menu_actions_emit_intent_signals() -> None:
    """Triggering menu actions should emit intents without owning file behavior."""

    app()
    button = AppOrbMenuButton()
    emitted: list[str] = []
    button.openRequested.connect(lambda: emitted.append("open"))
    button.saveRequested.connect(lambda: emitted.append("save"))
    button.saveAsRequested.connect(lambda: emitted.append("save-as"))
    button.exportRequested.connect(lambda: emitted.append("export"))
    button.settingsRequested.connect(lambda: emitted.append("settings"))
    button.comfyUiSettingsRequested.connect(lambda: emitted.append("comfy-settings"))
    button.restartGuiRequested.connect(lambda: emitted.append("restart-gui"))
    button.restartComfyRequested.connect(lambda: emitted.append("restart-comfy"))

    button._open_action.trigger()
    button._save_action.trigger()
    button._save_as_action.trigger()
    button._export_action.trigger()
    button._settings_action.trigger()
    button._comfyui_settings_action.trigger()
    button._restart_gui_action.trigger()
    button._restart_comfyui_action.trigger()

    assert emitted == [
        "open",
        "save",
        "save-as",
        "export",
        "settings",
        "comfy-settings",
        "restart-gui",
        "restart-comfy",
    ]

    button.close()


def test_app_orb_menu_workflow_file_actions_can_be_disabled() -> None:
    """Settings route policy should gray out workflow-only file commands."""

    app()
    button = AppOrbMenuButton()

    button.set_workflow_file_actions_enabled(False)

    assert button._open_action.isEnabled() is True
    assert button._save_action.isEnabled() is False
    assert button._save_as_action.isEnabled() is False
    assert button._export_action.isEnabled() is False
    assert button._settings_action.isEnabled() is True
    assert button._comfyui_settings_action.isEnabled() is True
    assert button._restart_gui_action.isEnabled() is True
    assert button._restart_comfyui_action.isEnabled() is True
    button.set_workflow_file_actions_enabled(True)

    assert button._save_action.isEnabled() is True
    assert button._save_as_action.isEnabled() is True
    assert button._export_action.isEnabled() is True

    button.close()


def test_app_orb_menu_button_reuses_shared_application_icon() -> None:
    """The orb should paint the same app icon resource used by the shell."""

    app()
    button = AppOrbMenuButton()

    assert button._orb_renderer.app_icon().cacheKey() == button._app_icon.cacheKey()

    button.close()


def test_app_orb_menu_button_connects_theme_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Theme and accent changes should invalidate cached orb art."""

    import substitute.presentation.shell.app_orb_menu as orb_menu_module

    app()
    callbacks: list[tuple[AppOrbMenuButton, object]] = []

    def connect_theme_refresh(widget: object, refresh: object) -> None:
        """Capture the button's refresh callback instead of registering globally."""

        callbacks.append((cast(AppOrbMenuButton, widget), refresh))

    monkeypatch.setattr(orb_menu_module, "connect_theme_refresh", connect_theme_refresh)
    button = AppOrbMenuButton()

    assert callbacks == [(button, button._refresh_orb_theme)]

    button.close()


def test_app_orb_hit_button_uses_circular_target() -> None:
    """The square overlay widget should only accept clicks inside its circle."""

    app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)

    assert button.hitButton(button.rect().center()) is True
    assert button.hitButton(QPoint(0, 0)) is False

    button.close()
