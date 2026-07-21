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

"""Install and reconcile managed-local Comfy workspaces through a workspace venv."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Callable

from substitute.application.onboarding.managed_runtime_state_recorder import (
    ManagedRuntimeStateRecorder,
    NoOpManagedRuntimeStateRecorder,
)
from substitute.domain.onboarding import ManagedRuntimeValidationStatus
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.comfy_manager import ComfyManagerRuntime
from substitute.infrastructure.comfy.hardware_detection import detect_hardware
from substitute.infrastructure.comfy.hardware_models import HardwareDetectionResult
from substitute.infrastructure.comfy.backend_model_root_configurator import (
    configure_backend_model_root,
)
from substitute.infrastructure.comfy.install_strategy import (
    ManagedInstallStrategy,
    select_install_strategy,
)
from substitute.infrastructure.comfy.managed_install_commands import (
    ensure_workspace_virtualenv,
    install_selected_torch_backend,
    install_workspace_requirements,
    upgrade_workspace_packaging_tools,
)
from substitute.infrastructure.comfy.managed_acceleration_reconciler import (
    reconcile_managed_acceleration_stack,
)
from substitute.infrastructure.comfy.managed_install_failures import (
    ManagedInstallStorageError,
)
from substitute.infrastructure.comfy.managed_install_scratch import (
    ManagedInstallScratch,
    default_installer_temp_root,
)
from substitute.infrastructure.comfy.managed_setup_state import (
    _managed_runtime_configuration_from_strategy,
)
from substitute.infrastructure.comfy.managed_workspace_operations import (
    migrate_nested_workspace_layout,
    remove_invalid_bootstrap_workspace,
    sync_managed_workspace_repository,
)
from substitute.infrastructure.comfy.managed_environment_validator import (
    ManagedEnvironmentValidationResult,
    validate_managed_environment,
)
from substitute.infrastructure.comfy.managed_existing_setup import (
    ExistingManagedSetupOperations,
    ExistingManagedSetupRequest,
    ResolvedTorchBackendContract,
    reconcile_existing_managed_setup,
)
from substitute.infrastructure.comfy.manager_provisioner import (
    ensure_managed_workspace_manager,
)
from substitute.infrastructure.comfy.workspace_dependency_reconciler import (
    reconcile_managed_workspace_dependencies,
)
from substitute.infrastructure.comfy.nodepack_reconciliation import (
    ensure_core_comfy_nodepacks,
    run_sugarcubes_baseline_maintenance,
)
from substitute.infrastructure.comfy.torch_policy import (
    TorchBackendPolicy,
    TorchReleaseChannel,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.standalone_environment.provisioner import (
    StandaloneEnvironmentProvisioner,
)
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_info,
    log_warning,
)
from substitute.shared.startup_trace import trace_span

StatusCallback = Callable[[str], None]
LogCallback = Callable[[str], None]

_LOGGER = get_logger("infrastructure.comfy.managed_install")


@dataclass(frozen=True)
class ResolvedTorchBackend:
    """Capture the backend candidate that ultimately validated for the workspace."""

    backend_key: str
    release_channel: TorchReleaseChannel
    selection_reason: str
    fallback_used: bool


class _ManagedExistingSetupOperations(ExistingManagedSetupOperations):
    """Adapt managed installer boundaries to the existing-setup transaction."""

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

        emit_status(self._on_status, message)

    def reconcile_dependencies(
        self,
        workspace: Path,
        python_executable: Path,
        env: Mapping[str, str],
    ) -> None:
        """Converge ComfyUI requirements through the infrastructure owner."""

        reconcile_managed_workspace_dependencies(
            workspace=workspace,
            python_executable=python_executable,
            on_log=self._on_log,
            env=env,
        )

    def provision_manager(self, workspace: Path, env: Mapping[str, str]) -> None:
        """Converge the Manager runtime through the public provisioning facade."""

        provision_workspace_manager(workspace, on_log=self._on_log, env=dict(env))

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
        workspace: Path,
        refresh_nodepacks: Collection[CoreNodepackId],
        env: Mapping[str, str],
    ) -> None:
        """Converge required nodepacks through their reconciliation owner."""

        ensure_core_comfy_nodepacks(
            workspace,
            refresh_nodepacks=refresh_nodepacks,
            on_log=self._on_log,
            env=env,
        )

    def prepare_sugarcubes(self, workspace: Path, env: Mapping[str, str]) -> None:
        """Converge SugarCubes baseline dependencies."""

        run_sugarcubes_baseline_maintenance(
            workspace,
            on_log=self._on_log,
            env=env,
        )

    def validate_torch(
        self,
        workspace: Path,
        policy: TorchBackendPolicy,
    ) -> tuple[ResolvedTorchBackendContract, ManagedEnvironmentValidationResult]:
        """Validate the existing torch backend."""

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
            env=dict(env),
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


def emit_status(callback: StatusCallback | None, message: str) -> None:
    """Emit user-facing status while also recording structured logs."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


def emit_log(callback: LogCallback | None, message: str) -> None:
    """Emit user-facing log line while retaining infrastructure log records."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


def provision_verified_standalone_workspace(
    workspace: Path,
    *,
    variant: StandaloneVariantId,
    on_log: LogCallback | None = None,
) -> Path:
    """Provision a new workspace from Comfy's checksum-verified environment."""

    return StandaloneEnvironmentProvisioner().provision(
        workspace=workspace,
        variant=variant,
        on_log=on_log,
    )


def prepare_dynamic_workspace_environment(
    *,
    workspace: Path,
    strategy: ManagedInstallStrategy,
    force_install: bool,
    on_status: StatusCallback | None,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> tuple[Path, ResolvedTorchBackend]:
    """Assemble a workspace environment when no standalone bundle is selected."""

    if force_install or not workspace_main_path(workspace).exists():
        emit_status(on_status, "Downloading or updating ComfyUI.")
        sync_managed_workspace_repository(
            workspace,
            on_log=on_log,
            env=dict(env) if env is not None else None,
        )
    emit_status(on_status, "Preparing ComfyUI's Python environment.")
    venv_python = ensure_workspace_virtualenv(
        workspace,
        python_runtime=strategy.python_runtime.executable,
        on_log=on_log,
        env=env,
    )
    upgrade_workspace_packaging_tools(venv_python, on_log=on_log, env=env)
    emit_status(on_status, "Installing the preferred torch backend.")
    resolved_backend = ResolvedTorchBackend(
        backend_key=strategy.torch_policy.backend_key,
        release_channel=strategy.torch_policy.release_channel,
        selection_reason=strategy.torch_policy.selection_reason,
        fallback_used=False,
    )
    try:
        install_selected_torch_backend(
            venv_python,
            install_arguments=strategy.torch_policy.install_arguments,
            on_log=on_log,
            env=env,
        )
    except ManagedInstallStorageError:
        raise
    except RuntimeError:
        if (
            strategy.torch_policy.fallback_install_arguments is None
            or strategy.torch_policy.fallback_release_channel is None
        ):
            raise
        emit_log(
            on_log,
            "[ManagedInstall] "
            f"Preferred torch backend `{strategy.torch_policy.backend_key}` failed "
            f"to install. Trying `{strategy.torch_policy.fallback_backend_key}`.",
        )
        emit_status(
            on_status,
            "The preferred torch backend could not be installed. Trying the "
            "configured fallback backend.",
        )
        install_selected_torch_backend(
            venv_python,
            install_arguments=strategy.torch_policy.fallback_install_arguments,
            on_log=on_log,
            env=env,
        )
        resolved_backend = ResolvedTorchBackend(
            backend_key=(
                strategy.torch_policy.fallback_backend_key
                or strategy.torch_policy.backend_key
            ),
            release_channel=strategy.torch_policy.fallback_release_channel,
            selection_reason=(
                strategy.torch_policy.fallback_selection_reason
                or strategy.torch_policy.selection_reason
            ),
            fallback_used=True,
        )
    emit_status(on_status, "Installing ComfyUI requirements.")
    install_workspace_requirements(
        venv_python,
        workspace=workspace,
        on_log=on_log,
        env=env,
    )
    return venv_python, resolved_backend


def provision_workspace_manager(
    workspace: Path,
    *,
    on_log: LogCallback | None = None,
    env: dict[str, str] | None = None,
    python_executable: Path | None = None,
) -> ComfyManagerRuntime:
    """Ensure the managed workspace uses ComfyUI's integrated Manager."""

    return ensure_managed_workspace_manager(
        workspace,
        python_executable=python_executable,
        on_log=on_log,
        env=env,
    )


def resolve_actual_torch_backend(
    *,
    policy: TorchBackendPolicy,
    validation: ManagedEnvironmentValidationResult,
) -> ResolvedTorchBackend:
    """Map one successful validation result back to the concrete torch policy used."""

    if validation.detected_torch_channel == policy.release_channel.value:
        return ResolvedTorchBackend(
            backend_key=policy.backend_key,
            release_channel=policy.release_channel,
            selection_reason=policy.selection_reason,
            fallback_used=False,
        )
    if (
        policy.fallback_release_channel is not None
        and validation.detected_torch_channel == policy.fallback_release_channel.value
    ):
        return ResolvedTorchBackend(
            backend_key=policy.fallback_backend_key or policy.backend_key,
            release_channel=policy.fallback_release_channel,
            selection_reason=policy.fallback_selection_reason
            or policy.selection_reason,
            fallback_used=True,
        )
    return ResolvedTorchBackend(
        backend_key=policy.backend_key,
        release_channel=policy.release_channel,
        selection_reason=policy.selection_reason,
        fallback_used=False,
    )


def install_and_validate_selected_torch_backend(
    *,
    python_executable: Path,
    workspace: Path,
    policy: TorchBackendPolicy,
    on_status: StatusCallback | None,
    on_log: LogCallback | None,
    env: dict[str, str] | None = None,
) -> tuple[ResolvedTorchBackend, ManagedEnvironmentValidationResult]:
    """Install the preferred torch backend, validate it, and try fallback when needed."""

    emit_status(
        on_status,
        "Installing the selected torch backend.",
    )
    try:
        install_selected_torch_backend(
            python_executable,
            install_arguments=policy.install_arguments,
            on_log=on_log,
            env=env,
        )
    except ManagedInstallStorageError:
        raise
    except RuntimeError:
        if (
            policy.fallback_install_arguments is None
            or policy.fallback_release_channel is None
        ):
            raise
        emit_log(
            on_log,
            "[ManagedInstall] "
            f"Preferred torch backend `{policy.backend_key}` failed to install. "
            f"Trying fallback `{policy.fallback_backend_key}`.",
        )
        emit_status(
            on_status,
            "The preferred torch backend could not be installed. Trying the "
            "configured fallback backend.",
        )
        install_selected_torch_backend(
            python_executable,
            install_arguments=policy.fallback_install_arguments,
            on_log=on_log,
            env=env,
        )
        fallback_validation = validate_managed_environment(
            workspace=workspace,
            expected_accelerator=policy.validation_expected,
            expected_torch_channel=policy.fallback_release_channel,
            on_log=on_log,
        )
        return (
            resolve_actual_torch_backend(policy=policy, validation=fallback_validation),
            fallback_validation,
        )
    emit_status(on_status, "Validating the managed ComfyUI environment.")
    validation = validate_managed_environment(
        workspace=workspace,
        expected_accelerator=policy.validation_expected,
        expected_torch_channel=policy.release_channel,
        on_log=on_log,
    )
    if validation.success:
        return resolve_actual_torch_backend(
            policy=policy, validation=validation
        ), validation
    if (
        policy.fallback_install_arguments is None
        or policy.fallback_release_channel is None
    ):
        return resolve_actual_torch_backend(
            policy=policy, validation=validation
        ), validation
    emit_log(
        on_log,
        "[ManagedInstall] "
        f"Preferred torch backend `{policy.backend_key}` did not validate. "
        f"Trying fallback `{policy.fallback_backend_key}`.",
    )
    emit_status(
        on_status,
        "Nightly torch did not validate. Falling back to the stable torch backend.",
    )
    install_selected_torch_backend(
        python_executable,
        install_arguments=policy.fallback_install_arguments,
        on_log=on_log,
        env=env,
    )
    fallback_validation = validate_managed_environment(
        workspace=workspace,
        expected_accelerator=policy.validation_expected,
        expected_torch_channel=policy.fallback_release_channel,
        on_log=on_log,
    )
    if fallback_validation.success:
        return (
            resolve_actual_torch_backend(policy=policy, validation=fallback_validation),
            fallback_validation,
        )
    return (
        resolve_actual_torch_backend(policy=policy, validation=fallback_validation),
        fallback_validation,
    )


def validate_existing_torch_backend(
    *,
    workspace: Path,
    policy: TorchBackendPolicy,
    on_log: LogCallback | None,
) -> tuple[ResolvedTorchBackend, ManagedEnvironmentValidationResult]:
    """Validate the existing workspace torch backend without forcing a reinstall."""

    validation = validate_managed_environment(
        workspace=workspace,
        expected_accelerator=policy.validation_expected,
        on_log=on_log,
    )
    return resolve_actual_torch_backend(
        policy=policy, validation=validation
    ), validation


def ensure_managed_comfy_setup(
    *,
    workspace: Path,
    managed_model_root: Path | None = None,
    configure_model_root: bool = False,
    force_cpu_mode: bool = False,
    prefer_edge_torch: bool = False,
    prefer_edge_comfy_channel: bool = False,
    refresh_core_nodepacks: Collection[CoreNodepackId] = frozenset(),
    installer_temp_root: Path | None = None,
    on_status: StatusCallback | None = None,
    on_log: LogCallback | None = None,
    state_recorder: ManagedRuntimeStateRecorder | None = None,
) -> Path:
    """Ensure ComfyUI and runtime dependencies are installed and ready."""

    scratch = ManagedInstallScratch(
        root=installer_temp_root or default_installer_temp_root(workspace)
    )
    with trace_span("managed_setup.scratch.create"):
        scratch.create()
    managed_env = scratch.apply_to()
    try:
        return _ensure_managed_comfy_setup(
            workspace=workspace,
            managed_model_root=managed_model_root,
            configure_model_root=configure_model_root,
            force_cpu_mode=force_cpu_mode,
            prefer_edge_torch=prefer_edge_torch,
            prefer_edge_comfy_channel=prefer_edge_comfy_channel,
            refresh_core_nodepacks=refresh_core_nodepacks,
            on_status=on_status,
            on_log=on_log,
            state_recorder=state_recorder,
            managed_env=managed_env,
        )
    finally:
        try:
            with trace_span("managed_setup.scratch.cleanup"):
                scratch.cleanup()
        except Exception as cleanup_error:
            log_warning(
                _LOGGER,
                "Managed install scratch cleanup failed.",
                scratch_root=scratch.root,
                error=cleanup_error,
            )


def _ensure_managed_comfy_setup(
    *,
    workspace: Path,
    managed_model_root: Path | None,
    configure_model_root: bool,
    force_cpu_mode: bool,
    prefer_edge_torch: bool,
    prefer_edge_comfy_channel: bool,
    refresh_core_nodepacks: Collection[CoreNodepackId],
    on_status: StatusCallback | None,
    on_log: LogCallback | None,
    state_recorder: ManagedRuntimeStateRecorder | None,
    managed_env: dict[str, str],
) -> Path:
    """Run managed ComfyUI setup with a prepared subprocess environment."""

    runtime_recorder = state_recorder or NoOpManagedRuntimeStateRecorder()
    workspace.parent.mkdir(parents=True, exist_ok=True)
    if migrate_nested_workspace_layout(workspace):
        emit_log(on_log, f"Migrated legacy nested ComfyUI layout in {workspace}.")
    force_install = os.getenv("SUGARSUB_FORCE_COMFY_INSTALL") == "1"
    venv_python = workspace_python_path(workspace)
    if (
        venv_python.exists()
        and workspace.exists()
        and workspace_main_path(workspace).exists()
        and not force_install
    ):
        return reconcile_existing_managed_setup(
            ExistingManagedSetupRequest(
                workspace=workspace,
                python_executable=venv_python,
                managed_model_root=managed_model_root,
                configure_model_root=configure_model_root,
                force_cpu_mode=force_cpu_mode,
                prefer_edge_torch=prefer_edge_torch,
                prefer_edge_comfy_channel=prefer_edge_comfy_channel,
                refresh_core_nodepacks=refresh_core_nodepacks,
                runtime_recorder=runtime_recorder,
                managed_env=managed_env,
            ),
            _ManagedExistingSetupOperations(
                on_status=on_status,
                on_log=on_log,
            ),
        )

    with trace_span("managed_setup.detect_hardware"):
        detection = detect_hardware()
    with trace_span("managed_setup.select_install_strategy"):
        strategy = select_install_strategy(
            detection=detection,
            force_cpu=force_cpu_mode,
            prefer_edge_torch=prefer_edge_torch,
            prefer_edge_comfy=prefer_edge_comfy_channel,
        )
    runtime_recorder.record_selection(
        _managed_runtime_configuration_from_strategy(
            workspace=workspace,
            detection=detection,
            strategy=strategy,
            force_cpu_mode=force_cpu_mode,
            prefer_edge_torch=prefer_edge_torch,
            prefer_edge_comfy_channel=prefer_edge_comfy_channel,
        )
    )
    try:
        if remove_invalid_bootstrap_workspace(workspace):
            emit_log(
                on_log,
                f"Removed incomplete managed workspace leftovers from {workspace}.",
            )
        if (
            workspace.exists()
            and not workspace_main_path(workspace).exists()
            and any(workspace.iterdir())
        ):
            raise RuntimeError(
                "The selected ComfyUI folder already contains files. Clear that folder "
                "or choose a different empty folder before trying again."
            )
        if workspace.exists() and workspace_main_path(workspace).exists():
            raise RuntimeError(
                "The managed ComfyUI folder contains an existing installation but "
                "does not contain Substitute's managed Python environment. Choose "
                "Use My Current ComfyUI for this folder, or choose an empty folder "
                "for managed setup."
            )

        emit_status(on_status, "Preparing the managed ComfyUI install strategy.")
        emit_log(
            on_log,
            "[ManagedInstall] "
            f"target={strategy.target.value} "
            f"python={strategy.python_runtime.selected_version} "
            f"channel={strategy.comfy_channel.value} "
            f"backend={strategy.torch_policy.backend_key} "
            f"torch_channel={strategy.torch_policy.release_channel.value} "
            f"stability={strategy.stability}",
        )

        if strategy.standalone_variant is not None:
            emit_status(
                on_status,
                "Installing Comfy's verified standalone Python environment.",
            )
            venv_python = provision_verified_standalone_workspace(
                workspace,
                variant=strategy.standalone_variant,
                on_log=on_log,
            )
            resolved_backend = ResolvedTorchBackend(
                backend_key=strategy.torch_policy.backend_key,
                release_channel=strategy.torch_policy.release_channel,
                selection_reason=(
                    "Installed the checksum-verified Comfy Desktop standalone "
                    f"environment {strategy.standalone_variant.value}."
                ),
                fallback_used=False,
            )
        else:
            venv_python, resolved_backend = prepare_dynamic_workspace_environment(
                workspace=workspace,
                strategy=strategy,
                force_install=force_install,
                on_status=on_status,
                on_log=on_log,
                env=managed_env,
            )
        selected_backend_key = resolved_backend.backend_key
        selected_torch_channel = resolved_backend.release_channel
        selected_torch_reason = resolved_backend.selection_reason
        selected_torch_fallback_used = resolved_backend.fallback_used
        emit_status(on_status, "Provisioning ComfyUI-Manager.")
        provision_workspace_manager(
            workspace,
            on_log=on_log,
            env=managed_env,
        )
        emit_status(on_status, "Installing Substitute Comfy nodepacks.")
        ensure_core_comfy_nodepacks(
            workspace,
            refresh_nodepacks=refresh_core_nodepacks,
            on_log=on_log,
            env=managed_env,
        )
        if configure_model_root:
            configure_backend_model_root(
                workspace=workspace,
                python_executable=venv_python,
                model_root=managed_model_root,
            )
        emit_status(on_status, "Preparing Base-Cubes dependencies.")
        run_sugarcubes_baseline_maintenance(
            workspace,
            on_log=on_log,
            env=managed_env,
        )
        emit_status(on_status, "Validating the managed ComfyUI environment.")
        validation = validate_managed_environment(
            workspace=workspace,
            expected_accelerator=strategy.torch_policy.validation_expected,
            expected_torch_channel=selected_torch_channel,
            on_log=on_log,
        )
        resolved_backend = ResolvedTorchBackend(
            backend_key=selected_backend_key,
            release_channel=selected_torch_channel,
            selection_reason=selected_torch_reason,
            fallback_used=selected_torch_fallback_used,
        )
        if (
            not validation.success
            and selected_torch_channel is strategy.torch_policy.release_channel
            and (
                strategy.torch_policy.fallback_install_arguments is not None
                and strategy.torch_policy.fallback_release_channel is not None
            )
        ):
            emit_log(
                on_log,
                "[ManagedInstall] "
                f"Preferred torch backend `{strategy.torch_policy.backend_key}` did "
                "not validate after install. Trying the configured fallback.",
            )
            install_selected_torch_backend(
                venv_python,
                install_arguments=strategy.torch_policy.fallback_install_arguments,
                on_log=on_log,
                env=managed_env,
            )
            validation = validate_managed_environment(
                workspace=workspace,
                expected_accelerator=strategy.torch_policy.validation_expected,
                expected_torch_channel=strategy.torch_policy.fallback_release_channel,
                on_log=on_log,
            )
            resolved_backend = ResolvedTorchBackend(
                backend_key=(
                    strategy.torch_policy.fallback_backend_key
                    or strategy.torch_policy.backend_key
                ),
                release_channel=strategy.torch_policy.fallback_release_channel,
                selection_reason=(
                    strategy.torch_policy.fallback_selection_reason
                    or strategy.torch_policy.selection_reason
                ),
                fallback_used=True,
            )
        runtime_recorder.record_torch_resolution(
            backend_policy=resolved_backend.backend_key,
            torch_release_channel=resolved_backend.release_channel.value,
            torch_selection_reason=resolved_backend.selection_reason,
            torch_fallback_used=resolved_backend.fallback_used,
        )
        runtime_recorder.record_validation(
            status=(
                ManagedRuntimeValidationStatus.VALID
                if validation.success
                else ManagedRuntimeValidationStatus.INVALID_BACKEND
            ),
            detail=validation.detail,
        )
        if not validation.success:
            raise RuntimeError(validation.detail)
        with trace_span("managed_setup.acceleration"):
            reconcile_managed_acceleration_stack(
                workspace=workspace,
                detection=detection,
                on_status=on_status,
                on_log=on_log,
                env=managed_env,
            )
        return venv_python
    except Exception as error:
        runtime_recorder.record_failure(
            status=ManagedRuntimeValidationStatus.INSTALL_FAILED,
            detail=str(error).strip() or type(error).__name__,
        )
        raise
