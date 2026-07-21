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

"""Install Manager-owned requirements without deciding runtime policy."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import os
from pathlib import Path
import subprocess

from substitute.infrastructure.comfy.manager_environment import (
    integrated_manager_pygit2_requirement,
    manager_runtime_environment,
)
from substitute.infrastructure.comfy.manager_runtime_probe import command_output
from substitute.shared.logging.logger import get_logger, log_info
from sugarsubstitute_shared.windows_long_paths import (
    subprocess_path,
    subprocess_working_directory,
)

LogCallback = Callable[[str], None]

_LOGGER = get_logger("infrastructure.comfy.manager_requirements_installer")


class ComfyManagerRequirementsInstaller:
    """Install authoritative Manager dependencies through a workspace Python."""

    def install_requirements(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        requirements_path: Path,
        on_log: LogCallback | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Install one requirements file exactly as declared by its owner."""

        self._install(
            workspace=workspace,
            python_executable=python_executable,
            arguments=("-r", subprocess_path(requirements_path)),
            on_log=on_log,
            env=env,
        )

    def install_pygit2_backend(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        on_log: LogCallback | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Install the app-tested backend only for Managers that expose it."""

        self._install(
            workspace=workspace,
            python_executable=python_executable,
            arguments=(integrated_manager_pygit2_requirement(),),
            on_log=on_log,
            env=env,
        )

    def _install(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        arguments: tuple[str, ...],
        on_log: LogCallback | None,
        env: Mapping[str, str] | None,
    ) -> None:
        """Run one hidden pip transaction and expose bounded diagnostics."""

        result = subprocess.run(
            [
                subprocess_path(python_executable),
                "-m",
                "pip",
                "install",
                *arguments,
            ],
            cwd=subprocess_working_directory(workspace),
            env=manager_runtime_environment(workspace, env, use_pygit2=False),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=1_800,
            check=False,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        )
        self._log_output(result, on_log)
        if result.returncode != 0:
            raise RuntimeError(
                "Substitute could not install ComfyUI Manager requirements. "
                + command_output(result)
            )

    @staticmethod
    def _log_output(
        result: subprocess.CompletedProcess[str],
        callback: LogCallback | None,
    ) -> None:
        """Emit non-empty command output to structured and setup logs."""

        for stream in (result.stdout, result.stderr):
            for line in (stream or "").splitlines():
                message = line.strip()
                if not message:
                    continue
                log_info(_LOGGER, message)
                if callback is not None:
                    callback(message)


__all__ = ["ComfyManagerRequirementsInstaller", "LogCallback"]
