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

"""Resolve launcher-owned install paths."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

from launcher.sugarsubstitute_launcher.platforms import (
    LauncherOperatingSystem,
    LauncherTarget,
    detect_launcher_target,
)

APP_DIR_NAME = "app"
APPDATA_DIR_NAME = "appdata"
LAUNCHER_DIR_NAME = "launcher"
RUNTIME_DIR_NAME = "runtime"
USER_DIR_NAME = "user"


@dataclass(frozen=True, slots=True)
class InstallLayout:
    """Name every path owned by one installed launcher root."""

    root: Path
    target: LauncherTarget = field(default_factory=detect_launcher_target)

    @classmethod
    def from_root(
        cls,
        root: Path,
        *,
        target: LauncherTarget | None = None,
    ) -> Self:
        """Create an install layout from a user-selected root path."""

        return cls(
            root=root.expanduser().resolve(),
            target=target or detect_launcher_target(),
        )

    @property
    def executable_path(self) -> Path:
        """Return the installed launcher executable path."""

        return self.root / self.target.executable_relative_path

    @property
    def bundle_path(self) -> Path:
        """Return the installed launcher bundle root for this target."""

        if self.target.bundle_root == Path("."):
            return self.root
        return self.root / self.target.bundle_root

    @property
    def launcher_support_path(self) -> Path:
        """Return the installed launcher support directory for this target."""

        return self.root / self.target.support_relative_path

    @property
    def launcher_dir(self) -> Path:
        """Return the launcher-owned mutable state directory."""

        return self.root / LAUNCHER_DIR_NAME

    @property
    def config_path(self) -> Path:
        """Return the launcher config path."""

        return self.launcher_dir / "config.json"

    @property
    def state_path(self) -> Path:
        """Return the launcher operational state path."""

        return self.launcher_dir / "state.json"

    @property
    def launcher_installation_path(self) -> Path:
        """Return the independently versioned launcher installation record."""

        return self.launcher_dir / "installation.json"

    @property
    def launcher_update_request_path(self) -> Path:
        """Return the single pending launcher replacement request path."""

        return self.launcher_dir / "updates" / "pending.json"

    @property
    def logs_dir(self) -> Path:
        """Return the launcher log directory."""

        return self.launcher_dir / "logs"

    @property
    def cache_dir(self) -> Path:
        """Return the launcher cache directory."""

        return self.launcher_dir / "cache"

    @property
    def downloads_dir(self) -> Path:
        """Return the launcher download staging directory."""

        return self.launcher_dir / "downloads"

    @property
    def locks_dir(self) -> Path:
        """Return the launcher lock directory."""

        return self.launcher_dir / "locks"

    @property
    def runtime_dir(self) -> Path:
        """Return the launcher-managed runtime directory."""

        return self.root / RUNTIME_DIR_NAME

    @property
    def runtime_python(self) -> Path:
        """Return the app venv Python path for this target."""

        return self.runtime_dir / self.target.runtime_python_relative_path

    @property
    def runtime_gui_python(self) -> Path:
        """Return the app venv GUI Python path for windowed app launch."""

        return self.runtime_dir / self.target.runtime_gui_python_relative_path

    @property
    def uv_executable(self) -> Path:
        """Return the launcher-managed uv executable path for this target."""

        return self.runtime_dir / "uv" / self.target.uv_executable_name

    @property
    def app_dir(self) -> Path:
        """Return the replaceable source payload directory."""

        return self.root / APP_DIR_NAME

    @property
    def app_entrypoint(self) -> Path:
        """Return the installed source payload entrypoint."""

        return self.app_dir / "main.py"

    @property
    def user_dir(self) -> Path:
        """Return the durable user data directory."""

        return self.root / USER_DIR_NAME

    @property
    def appdata_dir(self) -> Path:
        """Return the durable app state directory."""

        return self.root / APPDATA_DIR_NAME

    def create_base_directories(self) -> None:
        """Create launcher-owned directories without touching app payload data."""

        for directory in (
            self.root,
            self.launcher_dir,
            self.logs_dir,
            self.cache_dir,
            self.downloads_dir,
            self.locks_dir,
            self.runtime_dir,
            self.user_dir,
            self.appdata_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def default_install_root(
    executable_path: Path | None = None,
    *,
    target: LauncherTarget | None = None,
) -> Path:
    """Return the default install root for a setup executable."""

    resolved_target = target or detect_launcher_target()
    if (
        resolved_target.operating_system is LauncherOperatingSystem.WINDOWS
        and executable_path is not None
    ):
        executable_drive = executable_path.expanduser().drive
        if executable_drive:
            return Path(f"{executable_drive}\\") / "SugarSubstitute"

    if resolved_target.operating_system is LauncherOperatingSystem.MACOS:
        return Path.home() / "Applications" / "SugarSubstitute"
    if resolved_target.operating_system is LauncherOperatingSystem.LINUX:
        return Path.home() / ".local" / "share" / "SugarSubstitute"

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Programs" / "SugarSubstitute"
    return Path.home() / "AppData" / "Local" / "Programs" / "SugarSubstitute"
