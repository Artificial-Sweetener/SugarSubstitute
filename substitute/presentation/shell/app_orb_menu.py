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

"""Provide the shell-owned overlapping application orb menu button."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QPaintEvent, QPainter
from PySide6.QtWidgets import QAbstractButton, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.presentation.resources.app_icon import application_icon
from substitute.presentation.shell.app_orb_renderer import AppOrbRenderer
from substitute.presentation.shell.chrome_style import connect_theme_refresh
from substitute.presentation.shell.menu_button_controller import (
    ShellMenuButtonController,
)
from substitute.presentation.widgets.menu_model import (
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer

APP_ORB_MENU_OBJECT_NAME = "AppOrbMenuButton"
APP_ORB_MENU_ACCESSIBLE_NAME = "Application menu"
APP_ORB_MENU_OVERLAP_PX = 6
OPEN_SUGAR_SCRIPT_MENU_TEXT = "Open Sugar Script..."
SAVE_SUGAR_SCRIPT_MENU_TEXT = "Save Sugar Script"
SAVE_SUGAR_SCRIPT_AS_MENU_TEXT = "Save Sugar Script As..."
EXPORT_COMFY_WORKFLOW_MENU_TEXT = "Export to Comfy Workflow..."
SETTINGS_MENU_TEXT = "Settings"
COMFYUI_SETTINGS_MENU_TEXT = "ComfyUI Settings..."
RESTART_GUI_MENU_TEXT = "Restart the GUI"
RESTART_COMFYUI_MENU_TEXT = "Restart Comfy"


class AppOrbMenuButton(QAbstractButton):
    """Show the overlapping application orb and emit app-level command intents."""

    openRequested = Signal()
    saveRequested = Signal()
    saveAsRequested = Signal()
    exportRequested = Signal()
    settingsRequested = Signal()
    comfyUiSettingsRequested = Signal()
    restartGuiRequested = Signal()
    restartComfyRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the circular app orb and its command menu."""

        super().__init__(parent)
        self.setObjectName(APP_ORB_MENU_OBJECT_NAME)
        self.setToolTip(APP_ORB_MENU_ACCESSIBLE_NAME)
        self.setAccessibleName(APP_ORB_MENU_ACCESSIBLE_NAME)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._app_icon = application_icon()
        self._orb_renderer = AppOrbRenderer(self._app_icon)
        self._menu_controller = ShellMenuButtonController(
            self,
            menu_position=lambda: self.mapToGlobal(
                QPoint(0, self.height() - APP_ORB_MENU_OVERLAP_PX)
            ),
            qfluent_drop_down_vertical_offset=-APP_ORB_MENU_OVERLAP_PX,
        )
        self._configure_menu()
        self._menu_controller.set_menu(self._menu)
        self.clicked.connect(self._show_menu)
        connect_theme_refresh(self, self._refresh_orb_theme)

    def hitButton(self, pos: QPoint) -> bool:
        """Return whether ``pos`` is inside the circular orb target."""

        radius = min(self.width(), self.height()) / 2
        center = self.rect().center()
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        return (dx * dx) + (dy * dy) <= radius * radius

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the layered orb surface for the current interaction state."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        orb_pixmap = self._orb_renderer.render(
            self.size(),
            device_pixel_ratio=self.devicePixelRatioF(),
            enabled=self.isEnabled(),
            hovered=self.underMouse(),
            pressed=self.isDown() or self._menu_controller.is_menu_open(),
        )
        painter.drawPixmap(QPoint(0, 0), orb_pixmap)

    def _configure_menu(self) -> None:
        """Populate the command menu and connect actions to typed signals."""

        self._menu = QFluentMenuRenderer(parent=self).render(
            MenuModel(
                entries=(
                    MenuItem(
                        "app_orb.open",
                        OPEN_SUGAR_SCRIPT_MENU_TEXT,
                        callback=self._emit_open_requested,
                        icon=FIF.FOLDER,
                    ),
                    MenuItem(
                        "app_orb.save",
                        SAVE_SUGAR_SCRIPT_MENU_TEXT,
                        callback=self._emit_save_requested,
                        icon=FIF.SAVE,
                    ),
                    MenuItem(
                        "app_orb.save_as",
                        SAVE_SUGAR_SCRIPT_AS_MENU_TEXT,
                        callback=self._emit_save_as_requested,
                        icon=FIF.SAVE_AS,
                    ),
                    MenuItem(
                        "app_orb.export",
                        EXPORT_COMFY_WORKFLOW_MENU_TEXT,
                        callback=self._emit_export_requested,
                        icon=FIF.IOT,
                    ),
                    MenuSeparator(),
                    MenuItem(
                        "app_orb.settings",
                        SETTINGS_MENU_TEXT,
                        callback=self._emit_settings_requested,
                        icon=FIF.SETTING,
                    ),
                    MenuItem(
                        "app_orb.comfyui_settings",
                        COMFYUI_SETTINGS_MENU_TEXT,
                        callback=self._emit_comfyui_settings_requested,
                        icon=FIF.DEVELOPER_TOOLS,
                    ),
                    MenuSeparator(),
                    MenuItem(
                        "app_orb.restart_gui",
                        RESTART_GUI_MENU_TEXT,
                        callback=self._emit_restart_gui_requested,
                        icon=FIF.SYNC,
                    ),
                    MenuItem(
                        "app_orb.restart_comfy",
                        RESTART_COMFYUI_MENU_TEXT,
                        callback=self._emit_restart_comfy_requested,
                        icon=FIF.SYNC,
                    ),
                )
            )
        )
        self._open_action = self._rendered_menu_action("app_orb.open")
        self._save_action = self._rendered_menu_action("app_orb.save")
        self._save_as_action = self._rendered_menu_action("app_orb.save_as")
        self._export_action = self._rendered_menu_action("app_orb.export")
        self._settings_action = self._rendered_menu_action("app_orb.settings")
        self._comfyui_settings_action = self._rendered_menu_action(
            "app_orb.comfyui_settings"
        )
        self._restart_gui_action = self._rendered_menu_action("app_orb.restart_gui")
        self._restart_comfyui_action = self._rendered_menu_action(
            "app_orb.restart_comfy"
        )

    def _rendered_menu_action(self, action_id: str) -> QAction:
        """Return the renderer-created action with the requested stable id."""

        for action in self._menu.menuActions():
            if (
                isinstance(action, QAction)
                and action.property("menuActionId") == action_id
            ):
                return action
        raise RuntimeError(f"App orb menu action was not rendered: {action_id}")

    def set_workflow_file_actions_enabled(self, enabled: bool) -> None:
        """Enable workflow file commands only while a workflow route is active."""

        self._save_action.setEnabled(enabled)
        self._save_as_action.setEnabled(enabled)
        self._export_action.setEnabled(enabled)

    def _show_menu(self, _checked: bool = False) -> None:
        """Open the application command menu below the orb."""

        self._menu_controller.handle_button_clicked(_checked)

    def _refresh_orb_theme(self) -> None:
        """Refresh cached orb art after the Fluent theme or accent changes."""

        self._orb_renderer.clear_cache()
        self.update()

    def _emit_open_requested(self, *_args: object) -> None:
        """Emit the Open command intent."""

        self.openRequested.emit()

    def _emit_save_requested(self, *_args: object) -> None:
        """Emit the Save command intent."""

        self.saveRequested.emit()

    def _emit_save_as_requested(self, *_args: object) -> None:
        """Emit the Save As command intent."""

        self.saveAsRequested.emit()

    def _emit_export_requested(self, *_args: object) -> None:
        """Emit the Export command intent."""

        self.exportRequested.emit()

    def _emit_settings_requested(self, *_args: object) -> None:
        """Emit the Settings command intent."""

        self.settingsRequested.emit()

    def _emit_comfyui_settings_requested(self, *_args: object) -> None:
        """Emit the embedded ComfyUI Settings command intent."""

        self.comfyUiSettingsRequested.emit()

    def _emit_restart_gui_requested(self, *_args: object) -> None:
        """Emit the restart-GUI command intent."""

        self.restartGuiRequested.emit()

    def _emit_restart_comfy_requested(self, *_args: object) -> None:
        """Emit the restart-Comfy command intent."""

        self.restartComfyRequested.emit()


__all__ = [
    "APP_ORB_MENU_ACCESSIBLE_NAME",
    "APP_ORB_MENU_OBJECT_NAME",
    "APP_ORB_MENU_OVERLAP_PX",
    "COMFYUI_SETTINGS_MENU_TEXT",
    "EXPORT_COMFY_WORKFLOW_MENU_TEXT",
    "OPEN_SUGAR_SCRIPT_MENU_TEXT",
    "RESTART_COMFYUI_MENU_TEXT",
    "RESTART_GUI_MENU_TEXT",
    "SAVE_SUGAR_SCRIPT_AS_MENU_TEXT",
    "SAVE_SUGAR_SCRIPT_MENU_TEXT",
    "SETTINGS_MENU_TEXT",
    "AppOrbMenuButton",
]
