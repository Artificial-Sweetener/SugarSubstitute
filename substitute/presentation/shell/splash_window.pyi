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

from collections.abc import Callable
from typing import Any

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget

from substitute.domain.appearance import AppearanceThemeMode
from substitute.presentation.shell.window_effects import ShellBackdropMode
from sugarsubstitute_shared.launch_splash.activity import SplashActivity

class SplashWindow(QWidget):
    def __init__(
        self,
        icon: QIcon | None = ...,
        parent: QWidget | None = ...,
        *,
        backdrop_mode: ShellBackdropMode | None = ...,
        theme_mode: AppearanceThemeMode = ...,
        accent_color: str = ...,
        activity_clock: Callable[[], float] = ...,
    ) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def center_on_screen(self) -> None: ...
    def append_log(self, line: str) -> None: ...
    def start_activity(self, activity: SplashActivity) -> None: ...
    def clear_activity(self) -> None: ...
