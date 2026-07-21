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

"""Validate launcher-managed Substitute runtime state without reinstalling it."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys

from substitute.application.ports.runtime_provisioner import RuntimeProvisioner
from substitute.domain.onboarding import RuntimeBootstrapStatus, RuntimeConfiguration
from substitute.domain.onboarding.runtime_layout import runtime_layout_for_root
from sugarsubstitute_shared.windows_long_paths import subprocess_path


@dataclass(frozen=True)
class LauncherManagedRuntimeProvisioner(RuntimeProvisioner):
    """Validate the runtime created by the standalone launcher."""

    install_root: Path
    requirements_path: Path
    import_names: tuple[str, ...] = (
        "PySide6",
        "qfluentwidgets",
        "qpane",
        "substitute",
    )

    def provision(self, configuration: RuntimeConfiguration) -> RuntimeConfiguration:
        """Validate launcher-managed runtime files and return ready state."""

        layout = runtime_layout_for_root(configuration.runtime_root)
        if not layout.python_executable.is_file():
            raise RuntimeError(
                f"Launcher-managed runtime Python is missing: {layout.python_executable}"
            )
        if not self.requirements_path.is_file():
            raise RuntimeError(
                f"Launcher-managed requirements file is missing: {self.requirements_path}"
            )
        self._run_checked(
            [
                str(layout.python_executable),
                "-c",
                "; ".join(f"import {name}" for name in self.import_names),
            ],
            failure_message="Launcher-managed runtime is missing required imports.",
        )
        return RuntimeConfiguration(
            runtime_root=configuration.runtime_root,
            python_executable=layout.python_executable,
            bootstrap_status=RuntimeBootstrapStatus.READY,
            schema_version=configuration.schema_version,
        )

    def build_launch_command(
        self,
        configuration: RuntimeConfiguration,
        entrypoint_path: Path,
    ) -> list[str]:
        """Return the app launch command for the launcher-managed runtime."""

        python_executable = configuration.python_executable
        if python_executable is None:
            raise RuntimeError("Runtime configuration has no python executable.")
        return [
            subprocess_path(python_executable),
            subprocess_path(entrypoint_path),
            f"--install-root={subprocess_path(self.install_root)}",
        ]

    def _run_checked(
        self,
        command: list[str],
        *,
        failure_message: str,
    ) -> None:
        """Run one runtime validation command and raise a concise error."""

        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = subprocess.CREATE_NO_WINDOW
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.requirements_path.parent)
        try:
            subprocess.run(
                command,
                cwd=self.requirements_path.parent,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=creationflags,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise RuntimeError(failure_message) from error
