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

"""Adapt existing-workspace reconciliation to concrete infrastructure owners."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Callable

from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.comfy_manager import ComfyManagerRuntime
from substitute.infrastructure.comfy.backend_model_root_configurator import (
    configure_backend_model_root,
)
from substitute.infrastructure.comfy.hardware_detection import detect_hardware
from substitute.infrastructure.comfy.hardware_models import HardwareDetectionResult
from substitute.infrastructure.comfy.install_strategy import (
    ManagedInstallStrategy,
    select_install_strategy,
)
from substitute.infrastructure.comfy.managed_acceleration_reconciler import (
    reconcile_managed_acceleration_stack,
)
from substitute.infrastructure.comfy.managed_environment_validator import (
    ManagedEnvironmentValidationResult,
)
from substitute.infrastructure.comfy.managed_existing_setup import (
    ExistingManagedSetupOperations,
    ResolvedTorchBackendContract,
)
from substitute.infrastructure.comfy.managed_torch_reconciliation import (
    install_and_validate_selected_torch_backend,
    validate_existing_torch_backend,
)
from substitute.infrastructure.comfy.manager_provisioner import (
    ensure_managed_workspace_manager,
)
from substitute.infrastructure.comfy.nodepack_reconciliation import (
    ensure_core_comfy_nodepacks,
)
from substitute.infrastructure.comfy.sugarcubes_startup_maintenance import (
    attempt_sugarcubes_startup_maintenance,
)
from substitute.infrastructure.comfy.torch_policy import TorchBackendPolicy
from substitute.infrastructure.comfy.workspace_dependency_reconciler import (
    reconcile_managed_workspace_dependencies,
)
from substitute.shared.logging.logger import get_logger, log_info


StatusCallback = Callable[[str], None]
LogCallback = Callable[[str], None]
_LOGGER = get_logger("infrastructure.comfy.managed_existing_setup_operations")


class ManagedExistingSetupOperations(ExistingManagedSetupOperations):
    """Connect the existing-setup transaction to concrete mutable adapters."""

    def __init__(
        self,
        *,
        on_status: StatusCallback | None,
        on_log: LogCallback | None,
    ) -> None:
        """Capture reporting boundaries shared by setup operations."""

        self._on_status = on_status
        self._on_log = on_log

    def emit_status(self, message: str) -> None:
        """Publish one existing-workspace status message."""

        log_info(_LOGGER, message)
        if self._on_status is not None:
            self._on_status(message)

    def reconcile_dependencies(
        self,
        workspace: Path,
        python_executable: Path,
        env: Mapping[str, str],
    ) -> None:
        """Converge ComfyUI requirements through their infrastructure owner."""

        reconcile_managed_workspace_dependencies(
            workspace=workspace,
            python_executable=python_executable,
            on_log=self._on_log,
            env=env,
        )

    def provision_manager(
        self,
        workspace: Path,
        env: Mapping[str, str],
    ) -> ComfyManagerRuntime:
        """Converge the integrated Manager runtime."""

        return ensure_managed_workspace_manager(
            workspace,
            on_log=self._on_log,
            env=dict(env),
        )

    def configure_model_root(
        self,
        workspace: Path,
        python_executable: Path,
        model_root: Path | None,
    ) -> None:
        """Apply the configured model root through its adapter."""

        configure_backend_model_root(
            workspace=workspace,
            python_executable=python_executable,
            model_root=model_root,
        )

    def detect_hardware(self) -> HardwareDetectionResult:
        """Detect normalized host hardware."""

        return detect_hardware()

    def select_strategy(
        self,
        detection: HardwareDetectionResult,
        *,
        force_cpu: bool,
        prefer_edge_torch: bool,
        prefer_edge_comfy: bool,
    ) -> ManagedInstallStrategy:
        """Select the current managed install strategy."""

        return select_install_strategy(
            detection=detection,
            force_cpu=force_cpu,
            prefer_edge_torch=prefer_edge_torch,
            prefer_edge_comfy=prefer_edge_comfy,
        )

    def ensure_nodepacks(
        self,
        manager_runtime: ComfyManagerRuntime,
        refresh_nodepacks: Collection[CoreNodepackId],
        env: Mapping[str, str],
    ) -> None:
        """Converge required SugarSubstitute nodepacks."""

        ensure_core_comfy_nodepacks(
            manager_runtime=manager_runtime,
            refresh_nodepacks=refresh_nodepacks,
            on_log=self._on_log,
            env=env,
        )

    def prepare_sugarcubes(self, workspace: Path, env: Mapping[str, str]) -> None:
        """Converge SugarCubes baseline dependencies."""

        attempt_sugarcubes_startup_maintenance(
            workspace,
            on_log=self._on_log,
            env=env,
        )

    def validate_torch(
        self,
        workspace: Path,
        policy: TorchBackendPolicy,
    ) -> tuple[ResolvedTorchBackendContract, ManagedEnvironmentValidationResult]:
        """Validate the installed torch backend."""

        return validate_existing_torch_backend(
            workspace=workspace,
            policy=policy,
            on_log=self._on_log,
        )

    def install_and_validate_torch(
        self,
        python_executable: Path,
        workspace: Path,
        policy: TorchBackendPolicy,
        env: Mapping[str, str],
    ) -> tuple[ResolvedTorchBackendContract, ManagedEnvironmentValidationResult]:
        """Repair and validate the selected torch backend."""

        return install_and_validate_selected_torch_backend(
            python_executable=python_executable,
            workspace=workspace,
            policy=policy,
            on_status=self._on_status,
            on_log=self._on_log,
            env=env,
        )

    def reconcile_acceleration(
        self,
        workspace: Path,
        detection: HardwareDetectionResult,
        env: Mapping[str, str],
    ) -> None:
        """Converge optional acceleration artifacts."""

        reconcile_managed_acceleration_stack(
            workspace=workspace,
            detection=detection,
            on_status=self._on_status,
            on_log=self._on_log,
            env=env,
        )


__all__ = ["ManagedExistingSetupOperations"]
