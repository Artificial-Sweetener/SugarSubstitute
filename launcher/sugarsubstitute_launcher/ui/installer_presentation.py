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

"""Project installer workflow state into localized primary actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from launcher.sugarsubstitute_launcher.localized_text import launcher_text


class LauncherUiState(Enum):
    """Identify the user action currently owned by the primary button."""

    SELECT_LANGUAGE = "select_language"
    PREPARE_INSTALL = "prepare_install"
    INSTALL_APP = "install_app"
    INSTALL_RUNTIME = "install_runtime"
    START_SETUP = "start_setup"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class InstallerPrimaryAction:
    """Describe the localized primary button presentation."""

    text: str
    enabled: bool


def primary_action_for(state: LauncherUiState) -> InstallerPrimaryAction:
    """Return the primary action rendered for one installer state."""

    if state is LauncherUiState.SELECT_LANGUAGE:
        return InstallerPrimaryAction(launcher_text("Continue"), True)
    if state is LauncherUiState.PREPARE_INSTALL:
        return InstallerPrimaryAction(launcher_text("Install"), True)
    if state is LauncherUiState.INSTALL_APP:
        return InstallerPrimaryAction(launcher_text("Continue"), True)
    if state is LauncherUiState.INSTALL_RUNTIME:
        return InstallerPrimaryAction(launcher_text("Install runtime"), True)
    if state is LauncherUiState.START_SETUP:
        return InstallerPrimaryAction(launcher_text("Open setup"), True)
    return InstallerPrimaryAction(launcher_text("Setup started"), False)
