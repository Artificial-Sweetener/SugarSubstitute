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

"""Provision and verify the launcher-managed Python runtime."""

from __future__ import annotations

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import LauncherOperatingSystem
from launcher.sugarsubstitute_launcher.runtime_command import (
    SubprocessRuntimeCommandRunner,
)
from launcher.sugarsubstitute_launcher.runtime_models import (
    RuntimeCommandRunner,
    RuntimeProvisioningError,
    RuntimeProvisioningResult,
    UvExecutableProvider,
)
from launcher.sugarsubstitute_launcher.runtime_policy import (
    CRITICAL_IMPORTS,
    DEFAULT_PYTHON_VERSION,
    managed_venv_matches,
    runtime_environment,
    runtime_requirements_command,
    verify_runtime_imports,
)
from launcher.sugarsubstitute_launcher.uv_tool import VerifiedUvExecutableProvider
from sugarsubstitute_shared.windows_long_paths import subprocess_path


class UvManagedRuntimeInstaller:
    """Install Python, create the app venv, and install app requirements."""

    def __init__(
        self,
        *,
        python_version: str = DEFAULT_PYTHON_VERSION,
        uv_provider: UvExecutableProvider | None = None,
        runner: RuntimeCommandRunner | None = None,
    ) -> None:
        """Store runtime policy and the uv and command infrastructure ports."""

        self._python_version = python_version
        self._uv_provider = uv_provider or VerifiedUvExecutableProvider()
        self._runner = runner or SubprocessRuntimeCommandRunner()

    def provision(self, *, layout: InstallLayout) -> RuntimeProvisioningResult:
        """Ensure the launcher-managed runtime can run the installed app."""

        layout.create_base_directories()
        requirements_path = layout.app_dir / "requirements.txt"
        if not requirements_path.is_file():
            raise RuntimeProvisioningError(
                f"Requirements file is missing: {requirements_path}"
            )

        uv_executable = self._uv_provider.ensure(layout=layout)
        env = runtime_environment(layout=layout)
        python_install_command = [
            subprocess_path(uv_executable),
            "python",
            "install",
            self._python_version,
            "--install-dir",
            subprocess_path(layout.runtime_dir / "python"),
            "--managed-python",
            "--no-bin",
            "--no-config",
        ]
        if layout.target.operating_system is LauncherOperatingSystem.WINDOWS:
            python_install_command.insert(-1, "--no-registry")
        self._runner.run(
            python_install_command,
            cwd=layout.root,
            env=env,
        )
        venv_path = layout.runtime_dir / ".venv"
        if not managed_venv_matches(
            layout=layout,
            python_version=self._python_version,
        ):
            venv_command = [
                subprocess_path(uv_executable),
                "venv",
                subprocess_path(venv_path),
                "--python",
                self._python_version,
                "--managed-python",
                "--no-config",
            ]
            if venv_path.exists():
                venv_command.append("--clear")
            self._runner.run(
                venv_command,
                cwd=layout.root,
                env=env,
            )
        self._runner.run(
            runtime_requirements_command(
                uv_executable=uv_executable,
                layout=layout,
                requirements_path=requirements_path,
            ),
            cwd=layout.root,
            env=env,
        )
        verify_runtime_imports(
            python_executable=layout.runtime_python,
            imports=CRITICAL_IMPORTS,
            runner=self._runner,
            cwd=layout.root,
            env=env,
        )
        return RuntimeProvisioningResult(
            python_executable=layout.runtime_python,
            requirements_path=requirements_path,
        )
