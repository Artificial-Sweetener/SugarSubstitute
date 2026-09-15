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

"""Orchestrate reconciliation of an existing managed Comfy workspace."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sugarsubstitute_shared.localization import app_text, render_source_application_text

from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.comfy_manager import ComfyManagerRuntime
from substitute.domain.onboarding import (
    ManagedComfySetupResult,
    ManagedRuntimeConfiguration,
)
from substitute.infrastructure.comfy.hardware_models import HardwareDetectionResult
from substitute.infrastructure.comfy.install_strategy import ManagedInstallStrategy
from substitute.infrastructure.comfy.managed_environment_validator import (
    ManagedEnvironmentValidationResult,
)
from substitute.infrastructure.comfy.managed_startup_remote_steps import (
    ManagedStartupRemoteSteps,
)
from substitute.infrastructure.comfy.managed_runtime_configuration_codec import (
    managed_runtime_configuration_from_strategy,
    validated_managed_runtime_configuration,
)
from substitute.infrastructure.comfy.managed_setup_freshness_cache import (
    fresh_installed_setup_record,
    fresh_installed_setup_record_without_hardware_probe,
    try_write_installed_setup_freshness,
    validated_runtime_configuration_from_installed_setup_record,
    validation_from_installed_setup_record,
)
from substitute.infrastructure.comfy.managed_setup_freshness_inputs import (
    installed_setup_freshness_key,
    installed_setup_freshness_request,
)
from substitute.infrastructure.comfy.torch_policy import TorchBackendPolicy
from substitute.shared.startup_trace import trace_span
from sugarsubstitute_shared.startup_remote_access import StartupRemoteAccess


class ResolvedTorchBackendContract(Protocol):
    """Describe the validated torch choice needed by reconciliation."""

    @property
    def backend_key(self) -> str:
        """Return the selected backend identifier."""

    @property
    def selection_reason(self) -> str:
        """Return the reason for selecting this backend."""

    @property
    def fallback_used(self) -> bool:
        """Return whether validation required the fallback backend."""

    @property
    def release_channel(self) -> object:
        """Return an enum-like channel with a string value."""


class ExistingManagedSetupOperations(Protocol):
    """Expose mutable setup boundaries to the existing-workspace transaction."""

    def emit_status(self, message: str) -> None:
        """Publish one localized setup status."""

    def reconcile_dependencies(
        self,
        workspace: Path,
        python_executable: Path,
        env: Mapping[str, str],
    ) -> None:
        """Converge checkout-declared Python requirements."""

    def provision_manager(
        self,
        workspace: Path,
        env: Mapping[str, str],
    ) -> ComfyManagerRuntime:
        """Converge the checkout-declared Manager runtime."""

    def configure_model_root(
        self,
        workspace: Path,
        python_executable: Path,
        model_root: Path | None,
    ) -> None:
        """Configure the Substitute backend model root."""

    def detect_hardware(self) -> HardwareDetectionResult:
        """Detect host hardware for runtime selection."""

    def select_strategy(
        self,
        detection: HardwareDetectionResult,
        *,
        force_cpu: bool,
        prefer_edge_torch: bool,
        prefer_edge_comfy: bool,
    ) -> ManagedInstallStrategy:
        """Select the managed runtime strategy."""

    def ensure_nodepacks(
        self,
        manager_runtime: ComfyManagerRuntime,
        refresh_nodepacks: Collection[CoreNodepackId],
        env: Mapping[str, str],
    ) -> None:
        """Converge required SugarSubstitute nodepacks."""

    def prepare_sugarcubes(self, workspace: Path, env: Mapping[str, str]) -> None:
        """Converge SugarCubes baseline dependencies."""

    def validate_torch(
        self,
        workspace: Path,
        policy: TorchBackendPolicy,
    ) -> tuple[ResolvedTorchBackendContract, ManagedEnvironmentValidationResult]:
        """Validate the existing torch runtime."""

    def install_and_validate_torch(
        self,
        python_executable: Path,
        workspace: Path,
        policy: TorchBackendPolicy,
        env: Mapping[str, str],
    ) -> tuple[ResolvedTorchBackendContract, ManagedEnvironmentValidationResult]:
        """Repair and validate the selected torch runtime."""

    def reconcile_acceleration(
        self,
        workspace: Path,
        detection: HardwareDetectionResult,
        env: Mapping[str, str],
    ) -> None:
        """Converge optional native acceleration artifacts."""


@dataclass(frozen=True, slots=True)
class ExistingManagedSetupRequest:
    """Carry immutable inputs for one existing-workspace transaction."""

    workspace: Path
    setup_cache_record_path: Path
    python_executable: Path
    managed_model_root: Path | None
    configure_model_root: bool
    force_cpu_mode: bool
    prefer_edge_torch: bool
    prefer_edge_comfy_channel: bool
    repair_existing_runtime: bool
    refresh_core_nodepacks: Collection[CoreNodepackId]
    managed_env: Mapping[str, str]


def reconcile_existing_managed_setup(
    request: ExistingManagedSetupRequest,
    operations: ExistingManagedSetupOperations,
) -> ManagedComfySetupResult:
    """Converge an updated managed checkout before committing success evidence."""

    workspace = request.workspace
    python_executable = request.python_executable
    remote_steps = ManagedStartupRemoteSteps(
        StartupRemoteAccess.from_environment(request.managed_env)
    )
    freshness_request = installed_setup_freshness_request(
        force_cpu_mode=request.force_cpu_mode,
        prefer_edge_torch=request.prefer_edge_torch,
        prefer_edge_comfy_channel=request.prefer_edge_comfy_channel,
    )
    fast_record = None
    if not request.configure_model_root and not request.repair_existing_runtime:
        fast_record = fresh_installed_setup_record_without_hardware_probe(
            workspace=workspace,
            record_path=request.setup_cache_record_path,
            request=freshness_request,
            refresh_core_nodepacks=request.refresh_core_nodepacks,
        )
    if fast_record is not None:
        cached_configuration = (
            validated_runtime_configuration_from_installed_setup_record(fast_record)
        )
        assert cached_configuration is not None
        operations.emit_status("Managed ComfyUI setup is current.")
        return ManagedComfySetupResult(python_executable, cached_configuration)

    operations.emit_status(
        render_source_application_text(
            app_text("Checking ComfyUI's Python environment.")
        )
    )
    remote_steps.run(
        operation="reconcile_dependencies",
        action=lambda: _reconcile_dependencies(
            operations=operations,
            workspace=workspace,
            python_executable=python_executable,
            managed_env=request.managed_env,
        ),
    )
    if not remote_steps.degraded:
        operations.emit_status("Provisioning ComfyUI-Manager.")
    manager_step = remote_steps.run(
        operation="provision_manager",
        action=lambda: _provision_manager(
            operations=operations,
            workspace=workspace,
            managed_env=request.managed_env,
        ),
    )
    manager_runtime = manager_step.value
    with trace_span("managed_setup.detect_hardware"):
        detection = operations.detect_hardware()
    with trace_span("managed_setup.select_install_strategy"):
        strategy = operations.select_strategy(
            detection,
            force_cpu=request.force_cpu_mode,
            prefer_edge_torch=request.prefer_edge_torch,
            prefer_edge_comfy=request.prefer_edge_comfy_channel,
        )
    runtime_configuration = managed_runtime_configuration_from_strategy(
        workspace=workspace,
        detection=detection,
        strategy=strategy,
        force_cpu_mode=request.force_cpu_mode,
        prefer_edge_torch=request.prefer_edge_torch,
        prefer_edge_comfy_channel=request.prefer_edge_comfy_channel,
    )
    freshness_key = installed_setup_freshness_key(
        workspace=workspace,
        strategy=strategy,
    )
    current_record = (
        fresh_installed_setup_record(
            record_path=request.setup_cache_record_path,
            key=freshness_key,
            refresh_core_nodepacks=request.refresh_core_nodepacks,
        )
        if not request.repair_existing_runtime
        else None
    )
    if current_record is not None:
        if request.configure_model_root:
            _configure_model_root(request, operations)
        existing_validation = validation_from_installed_setup_record(current_record)
        cached_configuration = (
            validated_runtime_configuration_from_installed_setup_record(current_record)
        )
        assert existing_validation is not None
        assert cached_configuration is not None
        if existing_validation is not None and not remote_steps.degraded:
            try_write_installed_setup_freshness(
                record_path=request.setup_cache_record_path,
                key=freshness_key,
                request=freshness_request,
                runtime_configuration=cached_configuration,
                validation=existing_validation,
            )
        operations.emit_status("Managed ComfyUI setup is current.")
        return ManagedComfySetupResult(python_executable, cached_configuration)

    if not remote_steps.degraded:
        operations.emit_status("Installing Substitute Comfy nodepacks.")
    remote_steps.run(
        operation="ensure_nodepacks",
        action=lambda: _ensure_nodepacks(
            operations=operations,
            request=request,
            manager_runtime=manager_runtime,
        ),
    )
    if not remote_steps.degraded:
        operations.emit_status("Preparing Base-Cubes dependencies.")
    remote_steps.run(
        operation="sugarcubes_baseline",
        action=lambda: _prepare_sugarcubes(
            operations=operations,
            workspace=workspace,
            managed_env=request.managed_env,
        ),
    )
    if request.configure_model_root:
        _configure_model_root(request, operations)
    with trace_span("managed_setup.existing.validate_torch"):
        resolved_backend, validation = operations.validate_torch(
            workspace,
            strategy.torch_policy,
        )
    if (
        not validation.success
        and request.repair_existing_runtime
        and not remote_steps.degraded
    ):
        repair = remote_steps.run(
            operation="install_and_validate_torch",
            action=lambda: operations.install_and_validate_torch(
                python_executable,
                workspace,
                strategy.torch_policy,
                request.managed_env,
            ),
        )
        if repair.completed and repair.value is not None:
            resolved_backend, validation = repair.value
    if not validation.success:
        raise RuntimeError(validation.detail)
    validated_configuration = _validated_runtime_configuration(
        runtime_configuration,
        resolved_backend,
        validation,
    )
    remote_steps.run(
        operation="reconcile_acceleration",
        action=lambda: _reconcile_acceleration(
            operations=operations,
            workspace=workspace,
            detection=detection,
            managed_env=request.managed_env,
        ),
    )
    freshness_key = installed_setup_freshness_key(
        workspace=workspace,
        strategy=strategy,
    )
    if not remote_steps.degraded:
        try_write_installed_setup_freshness(
            record_path=request.setup_cache_record_path,
            key=freshness_key,
            request=freshness_request,
            runtime_configuration=validated_configuration,
            validation=validation,
        )
    return ManagedComfySetupResult(python_executable, validated_configuration)


def _reconcile_dependencies(
    *,
    operations: ExistingManagedSetupOperations,
    workspace: Path,
    python_executable: Path,
    managed_env: Mapping[str, str],
) -> None:
    """Run dependency reconciliation inside its startup trace span."""

    with trace_span("managed_setup.existing.reconcile_dependencies"):
        operations.reconcile_dependencies(workspace, python_executable, managed_env)


def _provision_manager(
    *,
    operations: ExistingManagedSetupOperations,
    workspace: Path,
    managed_env: Mapping[str, str],
) -> ComfyManagerRuntime:
    """Run Manager provisioning inside its startup trace span."""

    with trace_span("managed_setup.existing.provision_manager"):
        return operations.provision_manager(workspace, managed_env)


def _ensure_nodepacks(
    *,
    operations: ExistingManagedSetupOperations,
    request: ExistingManagedSetupRequest,
    manager_runtime: ComfyManagerRuntime | None,
) -> None:
    """Run core nodepack reconciliation inside its startup trace span."""

    with trace_span("managed_setup.existing.ensure_nodepacks"):
        if manager_runtime is None:
            raise RuntimeError(
                "Managed nodepack setup requires a validated Manager runtime."
            )
        operations.ensure_nodepacks(
            manager_runtime,
            request.refresh_core_nodepacks,
            request.managed_env,
        )


def _prepare_sugarcubes(
    *,
    operations: ExistingManagedSetupOperations,
    workspace: Path,
    managed_env: Mapping[str, str],
) -> None:
    """Run optional SugarCubes preparation inside its startup trace span."""

    with trace_span("managed_setup.existing.sugarcubes_baseline"):
        operations.prepare_sugarcubes(workspace, managed_env)


def _configure_model_root(
    request: ExistingManagedSetupRequest,
    operations: ExistingManagedSetupOperations,
) -> None:
    """Apply the requested model root before reporting setup completion."""

    with trace_span("managed_setup.existing.configure_model_root"):
        operations.configure_model_root(
            request.workspace,
            request.python_executable,
            request.managed_model_root,
        )


def _reconcile_acceleration(
    *,
    operations: ExistingManagedSetupOperations,
    workspace: Path,
    detection: HardwareDetectionResult,
    managed_env: Mapping[str, str],
) -> None:
    """Run acceleration reconciliation inside its startup trace span."""

    with trace_span("managed_setup.existing.acceleration"):
        operations.reconcile_acceleration(workspace, detection, managed_env)


def _validated_runtime_configuration(
    configuration: ManagedRuntimeConfiguration,
    backend: ResolvedTorchBackendContract,
    validation: ManagedEnvironmentValidationResult,
) -> ManagedRuntimeConfiguration:
    """Return one complete configuration from successful validation."""

    release_channel = getattr(backend.release_channel, "value", None)
    if not isinstance(release_channel, str):
        raise RuntimeError("Resolved torch release channel is invalid.")
    return validated_managed_runtime_configuration(
        configuration,
        backend_policy=backend.backend_key,
        torch_release_channel=release_channel,
        torch_selection_reason=backend.selection_reason,
        torch_fallback_used=backend.fallback_used,
        validation_detail=validation.detail,
    )


__all__ = [
    "ExistingManagedSetupOperations",
    "ExistingManagedSetupRequest",
    "ResolvedTorchBackendContract",
    "reconcile_existing_managed_setup",
]
