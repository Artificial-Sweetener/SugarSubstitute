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

"""Select, install, and validate the managed workspace torch backend."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from substitute.infrastructure.comfy.managed_environment_validator import (
    ManagedEnvironmentValidationResult,
    validate_managed_environment,
)
from substitute.infrastructure.comfy.managed_install_commands import (
    install_selected_torch_backend,
)
from substitute.infrastructure.comfy.managed_install_failures import (
    ManagedInstallStorageError,
)
from substitute.infrastructure.comfy.torch_policy import (
    TorchBackendPolicy,
    TorchReleaseChannel,
)
from substitute.shared.logging.logger import get_logger, log_info


StatusCallback = Callable[[str], None]
LogCallback = Callable[[str], None]
_LOGGER = get_logger("infrastructure.comfy.managed_torch_reconciliation")


def _emit_status(callback: StatusCallback | None, message: str) -> None:
    """Publish one torch status through its callback and structured log."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


def _emit_log(callback: LogCallback | None, message: str) -> None:
    """Publish one torch detail through its callback and structured log."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


@dataclass(frozen=True)
class ResolvedTorchBackend:
    """Capture the backend candidate that ultimately validated."""

    backend_key: str
    release_channel: TorchReleaseChannel
    selection_reason: str
    fallback_used: bool


def resolve_actual_torch_backend(
    *,
    policy: TorchBackendPolicy,
    validation: ManagedEnvironmentValidationResult,
) -> ResolvedTorchBackend:
    """Map validation output to the concrete selected torch policy."""

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
    env: Mapping[str, str] | None = None,
) -> tuple[ResolvedTorchBackend, ManagedEnvironmentValidationResult]:
    """Install the preferred backend and validate its configured fallback."""

    _emit_status(on_status, "Installing the selected torch backend.")
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
        _emit_log(
            on_log,
            "[ManagedInstall] "
            f"Preferred torch backend `{policy.backend_key}` failed to install. "
            f"Trying fallback `{policy.fallback_backend_key}`.",
        )
        _emit_status(
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
    _emit_status(on_status, "Validating the managed ComfyUI environment.")
    validation = validate_managed_environment(
        workspace=workspace,
        expected_accelerator=policy.validation_expected,
        expected_torch_channel=policy.release_channel,
        on_log=on_log,
    )
    if validation.success:
        return resolve_actual_torch_backend(
            policy=policy,
            validation=validation,
        ), validation
    if (
        policy.fallback_install_arguments is None
        or policy.fallback_release_channel is None
    ):
        return resolve_actual_torch_backend(
            policy=policy,
            validation=validation,
        ), validation
    _emit_log(
        on_log,
        "[ManagedInstall] "
        f"Preferred torch backend `{policy.backend_key}` did not validate. "
        f"Trying fallback `{policy.fallback_backend_key}`.",
    )
    _emit_status(
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
    """Validate an installed workspace backend without forcing installation."""

    validation = validate_managed_environment(
        workspace=workspace,
        expected_accelerator=policy.validation_expected,
        on_log=on_log,
    )
    return resolve_actual_torch_backend(
        policy=policy,
        validation=validation,
    ), validation


def validate_new_workspace_torch(
    *,
    workspace: Path,
    python_executable: Path,
    policy: TorchBackendPolicy,
    resolved_backend: ResolvedTorchBackend,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
) -> tuple[ResolvedTorchBackend, ManagedEnvironmentValidationResult]:
    """Validate a newly provisioned backend and install its fallback once."""

    validation = validate_managed_environment(
        workspace=workspace,
        expected_accelerator=policy.validation_expected,
        expected_torch_channel=resolved_backend.release_channel,
        on_log=on_log,
    )
    if (
        validation.success
        or resolved_backend.release_channel is not policy.release_channel
        or policy.fallback_install_arguments is None
        or policy.fallback_release_channel is None
    ):
        return resolved_backend, validation
    _emit_log(
        on_log,
        "[ManagedInstall] "
        f"Preferred torch backend `{policy.backend_key}` did not validate after "
        "install. Trying the configured fallback.",
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
        ResolvedTorchBackend(
            backend_key=policy.fallback_backend_key or policy.backend_key,
            release_channel=policy.fallback_release_channel,
            selection_reason=policy.fallback_selection_reason
            or policy.selection_reason,
            fallback_used=True,
        ),
        fallback_validation,
    )


__all__ = [
    "ResolvedTorchBackend",
    "install_and_validate_selected_torch_backend",
    "resolve_actual_torch_backend",
    "validate_existing_torch_backend",
    "validate_new_workspace_torch",
]
