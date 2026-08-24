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

"""Provide deterministic external boundaries for managed-install orchestration."""

from __future__ import annotations

from itertools import count
from pathlib import Path
import sys

import pytest

from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.infrastructure.comfy import managed_existing_setup_operations
from substitute.infrastructure.comfy import managed_install
from substitute.infrastructure.comfy import managed_torch_reconciliation
from substitute.infrastructure.comfy import managed_workspace_provisioning
from substitute.infrastructure.comfy.comfy_channel_policy import ComfyChannel
from substitute.infrastructure.comfy.hardware_models import (
    AcceleratorClass,
    HardwareAdapterInfo,
    HardwareDetectionResult,
    HardwareToolingAvailability,
    ManagedPlatform,
)
from substitute.infrastructure.comfy.install_strategy import ManagedInstallStrategy
from substitute.infrastructure.comfy.install_targets import ManagedInstallTarget
from substitute.infrastructure.comfy.managed_environment_validator import (
    ManagedEnvironmentValidationResult,
)
from substitute.infrastructure.comfy.managed_setup_cache_storage import (
    prepare_managed_setup_cache,
)
from substitute.infrastructure.comfy.managed_validation import workspace_python_path
from substitute.infrastructure.comfy.python_policy import PythonRuntimeSelection
from substitute.infrastructure.comfy.torch_policy import (
    TorchBackendPolicy,
    TorchReleaseChannel,
)
from sugarsubstitute_shared.external_scratch import ExternalScratchWorkspace


def managed_setup_record_path(workspace: Path) -> Path:
    """Return the managed setup receipt path through its cache owner."""

    cache = prepare_managed_setup_cache(workspace)
    try:
        return cache.record_path
    finally:
        cache.close()


def manager_runtime(workspace: Path) -> ComfyManagerRuntime:
    """Build one validated integrated Manager runtime fixture."""

    return ComfyManagerRuntime(
        kind=ComfyManagerKind.INTEGRATED,
        workspace=workspace,
        python_executable=workspace_python_path(workspace),
        version="4.1",
    )


_NVIDIA_DETECTION = HardwareDetectionResult(
    platform=ManagedPlatform.WINDOWS,
    adapters=(
        HardwareAdapterInfo(
            name="Test NVIDIA",
            accelerator_class=AcceleratorClass.NVIDIA,
            is_discrete=True,
        ),
    ),
    tooling=HardwareToolingAvailability(
        nvidia_smi=False,
        amd_tooling=False,
        intel_xpu_tooling=False,
    ),
)
_EXPERIMENTAL_STRATEGY = ManagedInstallStrategy(
    target=ManagedInstallTarget.WINDOWS_NVIDIA,
    python_runtime=PythonRuntimeSelection(
        executable=sys.executable,
        selected_version="3.13",
        used_fallback=False,
    ),
    comfy_channel=ComfyChannel.LATEST,
    torch_policy=TorchBackendPolicy(
        backend_key="cuda_nightly_cu130",
        install_arguments=("torch-nightly",),
        release_channel=TorchReleaseChannel.NIGHTLY,
        selection_reason="NVIDIA installs default to nightly torch.",
        stability="experimental",
        validation_expected=AcceleratorClass.NVIDIA,
        fallback_backend_key="cuda_cu130",
        fallback_install_arguments=("torch",),
        fallback_release_channel=TorchReleaseChannel.STABLE,
        fallback_selection_reason="Nightly torch failed validation.",
    ),
    standalone_variant=None,
    stability="experimental",
    summary_reason="Test NVIDIA hardware selects the dynamic nightly strategy.",
)


def configure_managed_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Isolate orchestration contracts from hardware, remote work, and scratch paths."""

    monkeypatch.delenv("SUGARSUB_SHARED_MODELS_ROOT", raising=False)
    scratch_parent = tmp_path.parent / f"{tmp_path.name}-managed-install-scratch"
    scratch_indices = count()

    def allocate_scratch(_workspace: Path) -> ExternalScratchWorkspace:
        """Reserve one deterministic per-test external scratch workspace."""

        scratch_parent.mkdir(parents=True, exist_ok=True)
        return ExternalScratchWorkspace.reserve(
            scratch_parent / f"run-{next(scratch_indices)}"
        )

    validation = ManagedEnvironmentValidationResult(
        success=True,
        detail="ok",
        detected_backend="nvidia",
        detected_torch_channel=TorchReleaseChannel.NIGHTLY.value,
        torch_version="2.9.0.dev",
    )
    monkeypatch.setattr(
        managed_install, "allocate_managed_install_scratch", allocate_scratch
    )
    monkeypatch.setattr(managed_install, "detect_hardware", lambda: _NVIDIA_DETECTION)
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "detect_hardware",
        lambda: _NVIDIA_DETECTION,
    )
    monkeypatch.setattr(
        managed_install,
        "select_install_strategy",
        lambda **_kwargs: _EXPERIMENTAL_STRATEGY,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "select_install_strategy",
        lambda **_kwargs: _EXPERIMENTAL_STRATEGY,
    )
    monkeypatch.setattr(
        managed_torch_reconciliation,
        "validate_managed_environment",
        lambda **_kwargs: validation,
    )
    monkeypatch.setattr(
        managed_workspace_provisioning,
        "install_selected_torch_backend",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        managed_torch_reconciliation,
        "install_selected_torch_backend",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        managed_install,
        "ensure_core_comfy_nodepacks",
        lambda manager_runtime, refresh_nodepacks=frozenset(), on_log=None, env=None: (
            None
        ),
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "ensure_core_comfy_nodepacks",
        lambda manager_runtime, refresh_nodepacks=frozenset(), on_log=None, env=None: (
            None
        ),
    )
    monkeypatch.setattr(
        managed_install,
        "attempt_sugarcubes_startup_maintenance",
        lambda _workspace, on_log=None, env=None: True,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "attempt_sugarcubes_startup_maintenance",
        lambda _workspace, on_log=None, env=None: True,
    )
    monkeypatch.setattr(
        managed_install,
        "reconcile_managed_acceleration_stack",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "reconcile_managed_acceleration_stack",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        managed_existing_setup_operations,
        "reconcile_managed_workspace_dependencies",
        lambda **_kwargs: None,
    )


__all__ = ["configure_managed_install", "managed_setup_record_path", "manager_runtime"]
