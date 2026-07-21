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

"""Provision the visible Substitute runtime under the installation root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

from substitute.application.ports.runtime_provisioner import RuntimeProvisioner
from substitute.domain.onboarding import RuntimeBootstrapStatus, RuntimeConfiguration
from substitute.domain.onboarding.runtime_layout import runtime_layout_for_root
from sugarsubstitute_shared.windows_long_paths import subprocess_path


@dataclass
class SubstituteRuntimeProvisioner(RuntimeProvisioner):
    """Provision a `runtime/.venv` environment for Substitute."""

    requirements_path: Path

    def provision(self, configuration: RuntimeConfiguration) -> RuntimeConfiguration:
        """Create the visible runtime venv and install Substitute dependencies."""

        runtime_root = configuration.runtime_root
        runtime_root.mkdir(parents=True, exist_ok=True)
        layout = runtime_layout_for_root(runtime_root)
        venv_root = layout.venv_root
        python_executable = layout.python_executable
        self._ensure_virtual_environment_exists(
            venv_root=venv_root,
            python_executable=python_executable,
        )
        self._ensure_runtime_pip(python_executable)
        self._run_checked(
            [
                subprocess_path(python_executable),
                "-m",
                "pip",
                "install",
                "--upgrade",
                "pip",
                "setuptools",
            ],
            failure_message="Failed to upgrade runtime packaging tools.",
        )
        self._run_checked(
            [
                subprocess_path(python_executable),
                "-m",
                "pip",
                "install",
                "-r",
                str(self.requirements_path),
            ],
            failure_message="Failed to install Substitute runtime requirements.",
        )
        return RuntimeConfiguration(
            runtime_root=runtime_root,
            python_executable=python_executable,
            bootstrap_status=RuntimeBootstrapStatus.READY,
            schema_version=configuration.schema_version,
        )

    def build_launch_command(
        self,
        configuration: RuntimeConfiguration,
        entrypoint_path: Path,
    ) -> list[str]:
        """Return the runtime-scoped command used to launch Substitute."""

        if configuration.python_executable is None:
            raise RuntimeError("Runtime configuration has no python executable.")
        return [
            str(configuration.python_executable),
            subprocess_path(entrypoint_path),
            f"--install-root={configuration.runtime_root.parent}",
        ]

    def _ensure_virtual_environment_exists(
        self,
        *,
        venv_root: Path,
        python_executable: Path,
    ) -> None:
        """Create the runtime virtual environment when it does not exist yet."""

        if python_executable.exists():
            return
        self._run_checked(
            [sys.executable, "-m", "venv", subprocess_path(venv_root)],
            failure_message="Failed to create Substitute runtime virtual environment.",
        )
        if not venv_root.exists():
            raise RuntimeError("Runtime virtual environment directory was not created.")
        if not python_executable.exists():
            raise RuntimeError("Runtime python executable was not created.")

    def _ensure_runtime_pip(self, python_executable: Path) -> None:
        """Bootstrap `pip` inside the runtime venv when it is missing."""

        if self._runtime_has_pip(python_executable):
            return
        self._run_checked(
            [subprocess_path(python_executable), "-m", "ensurepip", "--upgrade"],
            failure_message="Failed to bootstrap pip inside the Substitute runtime environment.",
        )
        if not self._runtime_has_pip(python_executable):
            raise RuntimeError(
                "Substitute created the runtime Python environment, but pip is still unavailable."
            )

    def _runtime_has_pip(self, python_executable: Path) -> bool:
        """Return whether the runtime venv can execute `python -m pip` successfully."""

        result = subprocess.run(
            [subprocess_path(python_executable), "-m", "pip", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    def _run_checked(
        self,
        command: list[str],
        *,
        failure_message: str,
    ) -> None:
        """Run one runtime bootstrap command and raise a concise error on failure."""

        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as error:
            raise RuntimeError(failure_message) from error
