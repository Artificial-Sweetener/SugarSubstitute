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

"""Orchestrate Manager provisioning from checkout-owned capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from substitute.domain.comfy_manager import (
    ComfyManagerCapabilities,
    ComfyManagerProvisioningAction,
    ComfyManagerRuntime,
    select_attached_manager_action,
)
from substitute.infrastructure.comfy.manager_contract import ComfyManagerContract
from substitute.infrastructure.comfy.legacy_manager_installer import (
    LegacyComfyManagerInstaller,
)
from substitute.infrastructure.comfy.manager_requirements_installer import (
    ComfyManagerRequirementsInstaller,
    LogCallback,
)
from substitute.infrastructure.comfy.manager_runtime_probe import (
    ComfyManagerRuntimeProbe,
    validation_failure_message,
)
from substitute.infrastructure.comfy.workspace_python_resolver import (
    resolve_workspace_python,
)
from substitute.infrastructure.filesystem import remove_app_owned_path
from substitute.infrastructure.version_control import (
    RepositoryService,
    repository_service,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("infrastructure.comfy.manager_provisioner")
DEFAULT_MANAGER_REPOSITORY_URL = "https://github.com/ltdrdata/ComfyUI-Manager.git"


def ensure_managed_workspace_manager(
    workspace: Path,
    *,
    python_executable: Path | None = None,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> ComfyManagerRuntime:
    """Ensure an app-owned supported ComfyUI uses its integrated Manager."""

    contract = ComfyManagerContract(workspace)
    if not contract.supports_integrated_manager:
        raise RuntimeError(
            "Managed ComfyUI does not expose the required integrated Manager contract "
            "(--enable-manager and manager_requirements.txt)."
        )
    resolved_python = python_executable or resolve_workspace_python(workspace)
    runtime = _ensure_integrated_runtime(
        contract=contract,
        python_executable=resolved_python,
        on_log=on_log,
        env=env,
    )
    if contract.legacy_directory.exists():
        _emit_log(
            on_log,
            f"[Manager] Removing app-owned legacy Manager checkout: "
            f"{contract.legacy_directory}",
        )
        remove_app_owned_path(contract.legacy_directory)
    return runtime


def ensure_attached_workspace_manager(
    workspace: Path,
    *,
    python_executable: Path | None = None,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
    repository_url: str = DEFAULT_MANAGER_REPOSITORY_URL,
    repositories: RepositoryService | None = None,
) -> ComfyManagerRuntime:
    """Provision Manager without replacing user-owned attached checkouts."""

    resolved_python = python_executable or resolve_workspace_python(workspace)
    contract = ComfyManagerContract(workspace)
    probe = ComfyManagerRuntimeProbe()
    integrated = probe.integrated(
        workspace=workspace,
        python_executable=resolved_python,
        env=env,
    )
    legacy = probe.legacy(
        workspace=workspace,
        python_executable=resolved_python,
        env=env,
    )
    action = select_attached_manager_action(
        ComfyManagerCapabilities(
            supports_integrated=contract.supports_integrated_manager,
            integrated_healthy=integrated.runtime is not None,
            legacy_healthy=legacy.runtime is not None,
        )
    )
    if action is ComfyManagerProvisioningAction.USE_INTEGRATED:
        _emit_log(on_log, "[Manager] Using ComfyUI's integrated Manager package.")
        assert integrated.runtime is not None
        return _ensure_optional_pygit2_backend(
            integrated.runtime,
            probe=probe,
            installer=ComfyManagerRequirementsInstaller(),
            on_log=on_log,
            env=env,
        )
    if action is ComfyManagerProvisioningAction.USE_LEGACY:
        _emit_log(on_log, "[Manager] Using the attached legacy Manager custom node.")
        assert legacy.runtime is not None
        return legacy.runtime
    if action is ComfyManagerProvisioningAction.INSTALL_INTEGRATED:
        return _install_integrated_runtime(
            contract=contract,
            python_executable=resolved_python,
            on_log=on_log,
            env=env,
            probe=probe,
            installer=ComfyManagerRequirementsInstaller(),
        )
    return LegacyComfyManagerInstaller(
        repositories=repositories or repository_service()
    ).install(
        contract=contract,
        python_executable=resolved_python,
        repository_url=repository_url,
        on_log=on_log,
        env=env,
        previous_failure=legacy.failure,
    )


def _ensure_integrated_runtime(
    *,
    contract: ComfyManagerContract,
    python_executable: Path,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> ComfyManagerRuntime:
    """Install missing integrated dependencies and validate optional backends."""

    probe = ComfyManagerRuntimeProbe()
    installer = ComfyManagerRequirementsInstaller()
    integrated = probe.integrated(
        workspace=contract.workspace,
        python_executable=python_executable,
        env=env,
    )
    if integrated.runtime is None:
        return _install_integrated_runtime(
            contract=contract,
            python_executable=python_executable,
            on_log=on_log,
            env=env,
            probe=probe,
            installer=installer,
        )
    return _ensure_optional_pygit2_backend(
        integrated.runtime,
        probe=probe,
        installer=installer,
        on_log=on_log,
        env=env,
    )


def _install_integrated_runtime(
    *,
    contract: ComfyManagerContract,
    python_executable: Path,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
    probe: ComfyManagerRuntimeProbe,
    installer: ComfyManagerRequirementsInstaller,
) -> ComfyManagerRuntime:
    """Install the checkout's exact Manager requirements and validate them."""

    _emit_log(on_log, "[Manager] Installing ComfyUI's integrated Manager package.")
    installer.install_requirements(
        workspace=contract.workspace,
        python_executable=python_executable,
        requirements_path=contract.integrated_requirements_path,
        on_log=on_log,
        env=env,
    )
    integrated = probe.integrated(
        workspace=contract.workspace,
        python_executable=python_executable,
        env=env,
    )
    if integrated.runtime is None:
        raise RuntimeError(validation_failure_message("integrated", integrated.failure))
    return _ensure_optional_pygit2_backend(
        integrated.runtime,
        probe=probe,
        installer=installer,
        on_log=on_log,
        env=env,
    )


def _ensure_optional_pygit2_backend(
    runtime: ComfyManagerRuntime,
    *,
    probe: ComfyManagerRuntimeProbe,
    installer: ComfyManagerRequirementsInstaller,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> ComfyManagerRuntime:
    """Provision pygit2 only when the installed Manager advertises support."""

    if not runtime.supports_pygit2:
        return runtime
    backend = probe.pygit2_backend(runtime, env=env)
    if backend.runtime is None:
        _emit_log(on_log, "[Manager] Installing the integrated pygit2 backend.")
        installer.install_pygit2_backend(
            workspace=runtime.workspace,
            python_executable=runtime.python_executable,
            on_log=on_log,
            env=env,
        )
        backend = probe.pygit2_backend(runtime, env=env)
    if backend.runtime is None:
        raise RuntimeError(validation_failure_message("pygit2", backend.failure))
    return backend.runtime


def _emit_log(callback: LogCallback | None, message: str) -> None:
    """Emit one Manager provisioning line to structured and setup logs."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


__all__ = [
    "DEFAULT_MANAGER_REPOSITORY_URL",
    "ensure_attached_workspace_manager",
    "ensure_managed_workspace_manager",
]
