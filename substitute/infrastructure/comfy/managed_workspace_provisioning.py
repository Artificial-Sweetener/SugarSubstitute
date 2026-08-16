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

"""Provision new standalone or dynamic managed workspace environments."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Callable

from substitute.infrastructure.comfy.install_strategy import ManagedInstallStrategy
from substitute.infrastructure.comfy.managed_install_commands import (
    ensure_workspace_virtualenv,
    install_selected_torch_backend,
    install_workspace_requirements,
    upgrade_workspace_packaging_tools,
)
from substitute.infrastructure.comfy.managed_install_failures import (
    ManagedInstallStorageError,
)
from substitute.infrastructure.comfy.managed_torch_reconciliation import (
    ResolvedTorchBackend,
)
from substitute.infrastructure.comfy.managed_validation import workspace_main_path
from substitute.infrastructure.comfy.managed_workspace_operations import (
    sync_managed_workspace_repository,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.standalone_environment.provisioner import (
    StandaloneEnvironmentProvisioner,
)
from substitute.shared.logging.logger import get_logger, log_info


StatusCallback = Callable[[str], None]
LogCallback = Callable[[str], None]
_LOGGER = get_logger("infrastructure.comfy.managed_workspace_provisioning")


def _emit(callback: Callable[[str], None] | None, message: str) -> None:
    """Publish one provisioning message through its callback and log."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


def provision_verified_standalone_workspace(
    workspace: Path,
    *,
    variant: StandaloneVariantId,
    on_log: LogCallback | None = None,
) -> Path:
    """Provision a workspace from Comfy's checksum-verified environment."""

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
    """Assemble a workspace environment without a standalone bundle."""

    if force_install or not workspace_main_path(workspace).exists():
        _emit(on_status, "Downloading or updating ComfyUI.")
        sync_managed_workspace_repository(
            workspace,
            on_log=on_log,
            env=dict(env) if env is not None else None,
        )
    _emit(on_status, "Preparing ComfyUI's Python environment.")
    venv_python = ensure_workspace_virtualenv(
        workspace,
        python_runtime=strategy.python_runtime.executable,
        on_log=on_log,
        env=env,
    )
    upgrade_workspace_packaging_tools(venv_python, on_log=on_log, env=env)
    _emit(on_status, "Installing the preferred torch backend.")
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
        _emit(
            on_log,
            "[ManagedInstall] "
            f"Preferred torch backend `{strategy.torch_policy.backend_key}` failed "
            f"to install. Trying `{strategy.torch_policy.fallback_backend_key}`.",
        )
        _emit(
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
    _emit(on_status, "Installing ComfyUI requirements.")
    install_workspace_requirements(
        venv_python,
        workspace=workspace,
        on_log=on_log,
        env=env,
    )
    return venv_python, resolved_backend


__all__ = [
    "prepare_dynamic_workspace_environment",
    "provision_verified_standalone_workspace",
]
