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

"""Install and validate the user-scoped legacy Manager custom node."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from substitute.domain.comfy_manager import ComfyManagerRuntime
from substitute.infrastructure.comfy.manager_contract import ComfyManagerContract
from substitute.infrastructure.comfy.manager_requirements_installer import (
    ComfyManagerRequirementsInstaller,
    LogCallback,
)
from substitute.infrastructure.comfy.manager_runtime_probe import (
    ComfyManagerRuntimeProbe,
    validation_failure_message,
)
from substitute.infrastructure.version_control import (
    RepositoryOperationError,
    RepositoryService,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("infrastructure.comfy.legacy_manager_installer")


class LegacyComfyManagerInstaller:
    """Own cloning, dependency installation, and validation for Manager v3."""

    def __init__(
        self,
        *,
        repositories: RepositoryService,
        requirements_installer: ComfyManagerRequirementsInstaller | None = None,
        runtime_probe: ComfyManagerRuntimeProbe | None = None,
    ) -> None:
        """Store legacy installation boundary collaborators."""

        self._repositories = repositories
        self._requirements = (
            requirements_installer or ComfyManagerRequirementsInstaller()
        )
        self._probe = runtime_probe or ComfyManagerRuntimeProbe()

    def install(
        self,
        *,
        contract: ComfyManagerContract,
        python_executable: Path,
        repository_url: str,
        previous_failure: str,
        on_log: LogCallback | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ComfyManagerRuntime:
        """Install legacy Manager without replacing an existing checkout."""

        if contract.legacy_directory.exists():
            raise RuntimeError(
                validation_failure_message("legacy custom-node", previous_failure)
                + " The existing user-owned Manager directory was left unchanged."
            )
        contract.legacy_directory.parent.mkdir(parents=True, exist_ok=True)
        self._emit(
            on_log,
            f"[Manager] Installing legacy Manager into {contract.legacy_directory}.",
        )
        try:
            self._repositories.clone(
                repository_url,
                contract.legacy_directory,
                on_progress=on_log,
            )
        except RepositoryOperationError as error:
            raise RuntimeError(
                "Substitute could not install the required legacy ComfyUI-Manager "
                "custom node."
            ) from error
        requirements_path = contract.legacy_directory / "requirements.txt"
        if requirements_path.is_file():
            self._requirements.install_requirements(
                workspace=contract.workspace,
                python_executable=python_executable,
                requirements_path=requirements_path,
                on_log=on_log,
                env=env,
            )
        legacy = self._probe.legacy(
            workspace=contract.workspace,
            python_executable=python_executable,
            env=env,
        )
        if legacy.runtime is None:
            raise RuntimeError(validation_failure_message("legacy", legacy.failure))
        return legacy.runtime

    @staticmethod
    def _emit(callback: LogCallback | None, message: str) -> None:
        """Emit one legacy installation line to structured and setup logs."""

        log_info(_LOGGER, message)
        if callback is not None:
            callback(message)


__all__ = ["LegacyComfyManagerInstaller"]
