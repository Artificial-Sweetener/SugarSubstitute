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

from substitute.application.onboarding.managed_runtime_state_recorder import (
    ManagedRuntimeStateRecorder,
)
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.onboarding import ManagedRuntimeValidationStatus
from substitute.infrastructure.comfy.hardware_models import HardwareDetectionResult
from substitute.infrastructure.comfy.install_strategy import ManagedInstallStrategy
from substitute.infrastructure.comfy.managed_environment_validator import (
    ManagedEnvironmentValidationResult,
)
from substitute.infrastructure.comfy.managed_setup_state import (
    _fresh_installed_setup_record_without_hardware_probe,
    _installed_setup_freshness_is_current,
    _installed_setup_freshness_key,
    _installed_setup_freshness_request,
    _load_installed_setup_freshness,
    _managed_runtime_configuration_from_strategy,
    _record_cached_installed_setup_success,
    _validation_from_installed_setup_record,
    _write_installed_setup_freshness,
)
from substitute.infrastructure.comfy.torch_policy import TorchBackendPolicy
from substitute.shared.startup_trace import trace_span


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

    def provision_manager(self, workspace: Path, env: Mapping[str, str]) -> None:
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
        workspace: Path,
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
    python_executable: Path
    managed_model_root: Path | None
    configure_model_root: bool
    force_cpu_mode: bool
    prefer_edge_torch: bool
    prefer_edge_comfy_channel: bool
    refresh_core_nodepacks: Collection[CoreNodepackId]
    runtime_recorder: ManagedRuntimeStateRecorder
    managed_env: Mapping[str, str]


def reconcile_existing_managed_setup(
    request: ExistingManagedSetupRequest,
    operations: ExistingManagedSetupOperations,
) -> Path:
    """Converge an updated managed checkout before committing success evidence."""

    workspace = request.workspace
    python_executable = request.python_executable
    freshness_request = _installed_setup_freshness_request(
        force_cpu_mode=request.force_cpu_mode,
        prefer_edge_torch=request.prefer_edge_torch,
        prefer_edge_comfy_channel=request.prefer_edge_comfy_channel,
    )
    operations.emit_status(
        render_source_application_text(
            app_text("Checking ComfyUI's Python environment.")
        )
    )
    with trace_span("managed_setup.existing.reconcile_dependencies"):
        operations.reconcile_dependencies(
            workspace, python_executable, request.managed_env
        )
    operations.emit_status("Provisioning ComfyUI-Manager.")
    with trace_span("managed_setup.existing.provision_manager"):
        operations.provision_manager(workspace, request.managed_env)
    if request.configure_model_root:
        with trace_span("managed_setup.existing.configure_model_root"):
            operations.configure_model_root(
                workspace,
                python_executable,
                request.managed_model_root,
            )

    fast_record = _fresh_installed_setup_record_without_hardware_probe(
        workspace=workspace,
        request=freshness_request,
        refresh_core_nodepacks=request.refresh_core_nodepacks,
    )
    if fast_record is not None:
        _record_cached_installed_setup_success(
            runtime_recorder=request.runtime_recorder,
            record=fast_record,
        )
        operations.emit_status("Managed ComfyUI setup is current.")
        return python_executable

    with trace_span("managed_setup.detect_hardware"):
        detection = operations.detect_hardware()
    with trace_span("managed_setup.select_install_strategy"):
        strategy = operations.select_strategy(
            detection,
            force_cpu=request.force_cpu_mode,
            prefer_edge_torch=request.prefer_edge_torch,
            prefer_edge_comfy=request.prefer_edge_comfy_channel,
        )
    runtime_configuration = _managed_runtime_configuration_from_strategy(
        workspace=workspace,
        detection=detection,
        strategy=strategy,
        force_cpu_mode=request.force_cpu_mode,
        prefer_edge_torch=request.prefer_edge_torch,
        prefer_edge_comfy_channel=request.prefer_edge_comfy_channel,
    )
    request.runtime_recorder.record_selection(runtime_configuration)
    freshness_key = _installed_setup_freshness_key(
        workspace=workspace,
        strategy=strategy,
    )
    if _installed_setup_freshness_is_current(
        workspace=workspace,
        key=freshness_key,
        refresh_core_nodepacks=request.refresh_core_nodepacks,
    ):
        existing_record = _load_installed_setup_freshness(workspace)
        existing_validation = (
            _validation_from_installed_setup_record(existing_record)
            if existing_record is not None
            else None
        )
        if existing_validation is not None:
            _write_installed_setup_freshness(
                workspace=workspace,
                key=freshness_key,
                request=freshness_request,
                runtime_configuration=runtime_configuration,
                validation=existing_validation,
            )
        operations.emit_status("Managed ComfyUI setup is current.")
        return python_executable

    operations.emit_status("Installing Substitute Comfy nodepacks.")
    with trace_span("managed_setup.existing.ensure_nodepacks"):
        operations.ensure_nodepacks(
            workspace,
            request.refresh_core_nodepacks,
            request.managed_env,
        )
        if request.configure_model_root:
            operations.configure_model_root(
                workspace,
                python_executable,
                request.managed_model_root,
            )
    operations.emit_status("Preparing Base-Cubes dependencies.")
    with trace_span("managed_setup.existing.sugarcubes_baseline"):
        operations.prepare_sugarcubes(workspace, request.managed_env)
    with trace_span("managed_setup.existing.validate_torch"):
        resolved_backend, validation = operations.validate_torch(
            workspace,
            strategy.torch_policy,
        )
    _record_torch_outcome(request.runtime_recorder, resolved_backend, validation)
    if not validation.success:
        resolved_backend, validation = operations.install_and_validate_torch(
            python_executable,
            workspace,
            strategy.torch_policy,
            request.managed_env,
        )
        _record_torch_outcome(request.runtime_recorder, resolved_backend, validation)
    if not validation.success:
        raise RuntimeError(validation.detail)
    with trace_span("managed_setup.existing.acceleration"):
        operations.reconcile_acceleration(workspace, detection, request.managed_env)
    freshness_key = _installed_setup_freshness_key(
        workspace=workspace,
        strategy=strategy,
    )
    _write_installed_setup_freshness(
        workspace=workspace,
        key=freshness_key,
        request=freshness_request,
        runtime_configuration=runtime_configuration,
        validation=validation,
    )
    return python_executable


def _record_torch_outcome(
    recorder: ManagedRuntimeStateRecorder,
    backend: ResolvedTorchBackendContract,
    validation: ManagedEnvironmentValidationResult,
) -> None:
    """Record one torch resolution and validation result consistently."""

    release_channel = getattr(backend.release_channel, "value", None)
    if not isinstance(release_channel, str):
        raise RuntimeError("Resolved torch release channel is invalid.")
    recorder.record_torch_resolution(
        backend_policy=backend.backend_key,
        torch_release_channel=release_channel,
        torch_selection_reason=backend.selection_reason,
        torch_fallback_used=backend.fallback_used,
    )
    recorder.record_validation(
        status=(
            ManagedRuntimeValidationStatus.VALID
            if validation.success
            else ManagedRuntimeValidationStatus.INVALID_BACKEND
        ),
        detail=validation.detail,
    )


__all__ = [
    "ExistingManagedSetupOperations",
    "ExistingManagedSetupRequest",
    "ResolvedTorchBackendContract",
    "reconcile_existing_managed_setup",
]
