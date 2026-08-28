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

"""Verify the durable application version committed by an installed launcher."""

from __future__ import annotations

from pathlib import Path
import time

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


def assert_installed_version(install_root: Path, expected_version: str) -> None:
    """Require launcher state and app source to identify the expected release."""

    layout = InstallLayout.from_root(install_root)
    state = LauncherUpdateState.load(layout.state_path)
    if state.installed_app_version != expected_version:
        raise InstallerLifecycleError(
            "Launcher state version mismatch: "
            f"{state.installed_app_version} != {expected_version}."
        )
    expected_line = f'__version__ = "{expected_version}"'
    version_path = layout.app_dir / "substitute" / "_version.py"
    if expected_line not in version_path.read_text(encoding="utf-8"):
        raise InstallerLifecycleError(
            f"Installed app source does not identify version {expected_version}."
        )


def wait_for_installed_version(
    *,
    install_root: Path,
    expected_version: str,
    timeout_seconds: float,
) -> None:
    """Wait until candidate readiness has been committed to durable update state."""

    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            assert_installed_version(install_root, expected_version)
        except (InstallerLifecycleError, OSError) as error:
            last_error = error
            time.sleep(0.05)
            continue
        return
    raise InstallerLifecycleError(
        f"Installed update did not commit version {expected_version}."
    ) from last_error


__all__ = ["assert_installed_version", "wait_for_installed_version"]
