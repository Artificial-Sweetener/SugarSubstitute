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

from collections.abc import Collection
import os
from pathlib import Path
from typing import Callable

from substitute.application.onboarding.managed_runtime_state_recorder import (
    ManagedRuntimeStateRecorder,
    NoOpManagedRuntimeStateRecorder,
)
from substitute.domain.onboarding import ManagedRuntimeValidationStatus
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.infrastructure.comfy.hardware_detection import detect_hardware
from substitute.infrastructure.comfy.backend_model_root_configurator import (
    configure_backend_model_root,
)
from substitute.infrastructure.comfy.install_strategy import select_install_strategy
from substitute.infrastructure.comfy.managed_acceleration_reconciler import (
    reconcile_managed_acceleration_stack,
)
from substitute.infrastructure.comfy.managed_install_environment import (
    build_managed_install_environment,
)
from substitute.infrastructure.comfy.managed_install_scratch import (
    allocate_managed_install_scratch,
)
from substitute.infrastructure.comfy.managed_setup_state import (
    _managed_runtime_configuration_from_strategy,
)
from substitute.infrastructure.comfy.managed_workspace_operations import (
    migrate_nested_workspace_layout,
    remove_invalid_bootstrap_workspace,
)
from substitute.infrastructure.comfy.managed_existing_setup import (
    ExistingManagedSetupRequest,
    reconcile_existing_managed_setup,
)
from substitute.infrastructure.comfy.managed_existing_setup_operations import (
    ManagedExistingSetupOperations,
)
from substitute.infrastructure.comfy.managed_torch_reconciliation import (
    ResolvedTorchBackend,
    validate_new_workspace_torch,
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
from substitute.infrastructure.comfy.managed_workspace_provisioning import (
    prepare_dynamic_workspace_environment,
    provision_verified_standalone_workspace,
)
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning
from substitute.shared.startup_trace import trace_span

_LOGGER = get_logger("infrastructure.comfy.managed_install")
StatusCallback = Callable[[str], None]
LogCallback = Callable[[str], None]


def emit_status(callback: StatusCallback | None, message: str) -> None:
    """Emit user-facing status while also recording structured logs."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


def emit_log(callback: LogCallback | None, message: str) -> None:
    """Emit user-facing log output while retaining infrastructure records."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


def ensure_managed_comfy_setup(
    *,
    workspace: Path,
    managed_model_root: Path | None = None,
    configure_model_root: bool = False,
    force_cpu_mode: bool = False,
    prefer_edge_torch: bool = False,
    prefer_edge_comfy_channel: bool = False,
    refresh_core_nodepacks: Collection[CoreNodepackId] = frozenset(),
    on_status: StatusCallback | None = None,
    on_log: LogCallback | None = None,
    state_recorder: ManagedRuntimeStateRecorder | None = None,
) -> Path:
    """Ensure ComfyUI and runtime dependencies are installed and ready."""

    scratch = allocate_managed_install_scratch(workspace)
    with trace_span("managed_setup.scratch.create"):
        managed_env = build_managed_install_environment(scratch.root)
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
            ManagedExistingSetupOperations(
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
        emit_status(on_status, "Provisioning ComfyUI-Manager.")
        ensure_managed_workspace_manager(
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
        attempt_sugarcubes_startup_maintenance(
            workspace,
            on_log=on_log,
            env=managed_env,
        )
        emit_status(on_status, "Validating the managed ComfyUI environment.")
        resolved_backend, validation = validate_new_workspace_torch(
            workspace=workspace,
            python_executable=venv_python,
            policy=strategy.torch_policy,
            resolved_backend=resolved_backend,
            on_log=on_log,
            env=managed_env,
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
