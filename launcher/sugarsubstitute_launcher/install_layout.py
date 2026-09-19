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
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

from launcher.sugarsubstitute_launcher.platforms import (
    LauncherOperatingSystem,
    LauncherTarget,
    detect_launcher_target,
)
from sugarsubstitute_shared.windows_long_paths import operational_path

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
    launcher_bundle_root: Path | None = None
    release_root: Path | None = None

    @classmethod
    def from_root(
        cls,
        root: Path,
        *,
        target: LauncherTarget | None = None,
    ) -> Self:
        """Create an install layout from a user-selected root path."""

        resolved_root = operational_path(root).resolve()
        resolved_target = target or detect_launcher_target()
        bundle_root: Path | None = None
        if bool(getattr(sys, "frozen", False)):
            from sugarsubstitute_shared.launcher_update.bundle_paths import (
                LauncherBundlePaths,
            )
            from sugarsubstitute_shared.launcher_update.targets import (
                launcher_bundle_target_for_key,
            )

            bundle_root = LauncherBundlePaths(resolved_root).payload_for_executable(
                Path(sys.executable),
                launcher_bundle_target_for_key(resolved_target.key),
            )
        return cls(
            root=resolved_root, target=resolved_target, launcher_bundle_root=bundle_root
        )

    @property
    def executable_path(self) -> Path:
        """Return the installed launcher executable path."""

        return self.root / self.target.executable_relative_path

    @property
    def bundle_path(self) -> Path:
        """Return the installed launcher bundle root for this target."""

        root = self.launcher_bundle_root or self.root
        if self.target.bundle_root == Path("."):
            return root
        return root / self.target.bundle_root

    @property
    def launcher_support_path(self) -> Path:
        """Return the installed launcher support directory for this target."""

        return (
            self.launcher_bundle_root or self.root
        ) / self.target.support_relative_path

    @property
    def launcher_ui_executable_path(self) -> Path | None:
        """Return the packaged Qt launcher child when the target provides one."""

        relative_path = self.target.launcher_ui_executable_relative_path
        if relative_path is None:
            return None
        return self.bundle_path / relative_path

    @property
    def crashpad_runtime_path(self) -> Path:
        """Return the packaged native Crashpad runtime directory."""

        return self.launcher_support_path / "crashpad"

    @property
    def crashpad_handler_path(self) -> Path:
        """Return the platform Crashpad exception-handler executable."""

        executable_name = (
            "crashpad_handler.exe"
            if self.target.operating_system is LauncherOperatingSystem.WINDOWS
            else "crashpad_handler"
        )
        return self.crashpad_runtime_path / executable_name

    @property
    def crashpad_client_library_path(self) -> Path:
        """Return the platform SugarSubstitute Crashpad client bridge."""

        if self.target.operating_system is LauncherOperatingSystem.WINDOWS:
            filename = "sugarsubstitute_crashpad_client.dll"
        elif self.target.operating_system is LauncherOperatingSystem.MACOS:
            filename = "sugarsubstitute_crashpad_client.dylib"
        else:
            filename = "sugarsubstitute_crashpad_client.so"
        return self.crashpad_runtime_path / filename

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
    def runtime_dir(self) -> Path:
        """Return the launcher-managed runtime directory."""

        return self._selected_release_root() / RUNTIME_DIR_NAME

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

        return self._selected_release_root() / APP_DIR_NAME

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
            self.runtime_dir,
            self.user_dir,
            self.appdata_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def for_release_root(self, release_root: Path) -> InstallLayout:
        """Return this installation with explicit candidate app/runtime ownership."""

        resolved = release_root.expanduser().resolve()
        if resolved != self.root and not resolved.is_relative_to(self.root):
            raise ValueError("Application release root escapes its installation.")
        return InstallLayout(
            root=self.root,
            target=self.target,
            launcher_bundle_root=self.launcher_bundle_root,
            release_root=resolved,
        )

    def _selected_release_root(self) -> Path:
        """Resolve explicit preparation storage or the atomically selected release."""

        if self.release_root is not None:
            return self.release_root
        from launcher.sugarsubstitute_launcher.application_release_selection import (
            ApplicationReleaseSelection,
        )

        return ApplicationReleaseSelection(self.root).active_root()


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
