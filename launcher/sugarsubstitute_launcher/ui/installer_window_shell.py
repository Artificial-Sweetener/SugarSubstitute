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

"""Compose native installer chrome independently of workflow coordination."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QVBoxLayout
from qframelesswindow import AcrylicWindow  # type: ignore[import-untyped]
from qframelesswindow.titlebar import TitleBar  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.resources import launcher_icon
from launcher.sugarsubstitute_launcher.ui.installer_style import apply_installer_style
from launcher.sugarsubstitute_launcher.ui.installer_view import InstallerView
from sugarsubstitute_shared.presentation.installer_surface import (
    INSTALLER_WINDOW_HEIGHT,
    INSTALLER_WINDOW_WIDTH,
    configure_installer_title_bar,
)

if TYPE_CHECKING:
    from sugarsubstitute_shared.presentation.localization import TranslationManager


def build_installer_window_shell(
    window: AcrylicWindow,
    *,
    initial_install_path: str,
    localization_manager: TranslationManager | None,
    show_language_first: bool,
) -> InstallerView:
    """Return the composed view while leaving action routing to its coordinator."""
    window.setWindowTitle(launcher_text("SugarSubstitute Setup"))
    window.setWindowIcon(launcher_icon())
    window.resize(INSTALLER_WINDOW_WIDTH, INSTALLER_WINDOW_HEIGHT)
    window.setFixedSize(INSTALLER_WINDOW_WIDTH, INSTALLER_WINDOW_HEIGHT)
    title_bar = TitleBar(window)
    configure_installer_title_bar(title_bar)
    window.setTitleBar(title_bar)
    window.titleBar.maxBtn.hide()
    window.titleBar.minBtn.hide()
    view = InstallerView(
        initial_install_path=initial_install_path,
        localization_manager=localization_manager,
        show_language_first=show_language_first,
        parent=window,
    )
    body_layout = QVBoxLayout(window)
    body_layout.setContentsMargins(0, 0, 0, 0)
    body_layout.setSpacing(0)
    body_layout.addWidget(view)
    apply_installer_style(window, view)
    window.titleBar.raise_()
    return view
