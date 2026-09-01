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

"""Own deterministic managed-runtime commands, environment, and verification."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from sugarsubstitute_shared.windows_long_paths import subprocess_path

if TYPE_CHECKING:
    from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
    from launcher.sugarsubstitute_launcher.platforms import LauncherTarget
    from launcher.sugarsubstitute_launcher.runtime_models import RuntimeCommandRunner


DEFAULT_PYTHON_VERSION = "3.13.12"
CRITICAL_IMPORTS: tuple[str, ...] = (
    "PySide6",
    "qfluentwidgets",
    "cutecanvas",
    "substitute",
)


def runtime_requirements_command(
    *,
    uv_executable: Path,
    layout: InstallLayout,
    requirements_path: Path,
) -> list[str]:
    """Build the target-specific uv command for app runtime dependencies."""

    command = [
        subprocess_path(uv_executable),
        "pip",
        "install",
        "--python",
        subprocess_path(layout.runtime_python),
    ]
    command.extend(_torch_backend_arguments(layout.target))
    command.extend(["-r", subprocess_path(requirements_path)])
    return command


def runtime_environment(*, layout: InstallLayout) -> dict[str, str]:
    """Build the environment that keeps uv and Python state deterministic."""

    env = dict(os.environ)
    env.pop("UV_EXCLUDE_NEWER", None)
    env["UV_CACHE_DIR"] = subprocess_path(layout.cache_dir / "uv")
    env["UV_PYTHON_INSTALL_DIR"] = subprocess_path(layout.runtime_dir / "python")
    env["UV_NO_MODIFY_PATH"] = "1"
    env["VIRTUAL_ENV"] = subprocess_path(layout.runtime_dir / ".venv")
    env["PYTHONPATH"] = subprocess_path(layout.app_dir)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    return env


def managed_venv_matches(
    *,
    layout: InstallLayout,
    python_version: str,
) -> bool:
    """Return whether the existing managed venv already uses pinned Python."""

    if not layout.runtime_python.is_file():
        return False
    config_path = layout.runtime_dir / ".venv" / "pyvenv.cfg"
    try:
        config_lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    config = {
        key.strip().casefold(): value.strip()
        for line in config_lines
        if "=" in line
        for key, value in (line.split("=", maxsplit=1),)
    }
    return (
        config.get("implementation", "").casefold() == "cpython"
        and config.get("version_info") == python_version
    )


def verify_runtime_imports(
    *,
    python_executable: Path,
    imports: Sequence[str],
    runner: RuntimeCommandRunner,
    cwd: Path,
    env: Mapping[str, str],
) -> None:
    """Verify that the managed runtime can import critical packages."""

    import_statement = "; ".join(f"import {module_name}" for module_name in imports)
    runner.run(
        [subprocess_path(python_executable), "-c", import_statement],
        cwd=cwd,
        env=env,
    )


def _torch_backend_arguments(target: LauncherTarget) -> list[str]:
    """Select a portable PyTorch distribution for the app support runtime."""

    from launcher.sugarsubstitute_launcher.platforms import LauncherOperatingSystem

    if target.operating_system is LauncherOperatingSystem.LINUX:
        return ["--torch-backend", "cpu"]
    return []
