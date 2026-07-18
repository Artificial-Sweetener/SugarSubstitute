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

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QDockWidget, QWidget
from substitute.presentation.shell.shell_chrome_controller import ShellChromeController
from substitute.presentation.shell.shell_layout_restore_controller import (
    ShellLayoutRestoreController,
)
from substitute.presentation.shell.workspace_layout_controller import (
    WorkspaceLayoutController,
)

class MainWindow:
    shell_chrome_controller: ShellChromeController
    shell_layout_restore_controller: ShellLayoutRestoreController
    workspace_layout_controller: WorkspaceLayoutController
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def eventFilter(self, source: QObject, event: QEvent) -> bool: ...
    def get_active_workflow(self) -> object: ...
    def on_dock_closed(
        self, dock_widget: QDockWidget, content_widget: QWidget
    ) -> None: ...
    def request_session_autosave(self) -> None: ...
    def resizeEvent(self, event: QResizeEvent) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
