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

"""Validate the managed Comfy workspace backend and launchability."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable

from sugarsubstitute_shared.localization import app_text

from substitute.infrastructure.comfy.hardware_models import AcceleratorClass
from substitute.infrastructure.comfy.torch_policy import TorchReleaseChannel
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
)
from substitute.infrastructure.comfy.torch_runtime_probe import (
    TorchRuntimeDetails,
    query_torch_runtime,
)

LogCallback = Callable[[str], None]


@dataclass(frozen=True)
class ManagedEnvironmentValidationResult:
    """Describe the observed validation result for one managed workspace."""

    success: bool
    detail: str
    detected_backend: str
    detected_torch_channel: str
    torch_version: str | None
    device_name: str | None = None


def validate_managed_environment(
    *,
    workspace: Path,
    expected_accelerator: AcceleratorClass,
    expected_torch_channel: TorchReleaseChannel | None = None,
    on_log: LogCallback | None = None,
) -> ManagedEnvironmentValidationResult:
    """Validate the managed workspace backend and basic Comfy launchability."""

    python_executable = workspace_python_path(workspace)
    main_path = workspace_main_path(workspace)
    if not python_executable.exists():
        return ManagedEnvironmentValidationResult(
            success=False,
            detail="Managed workspace Python executable is missing.",
            detected_backend="missing",
            detected_torch_channel=TorchReleaseChannel.STABLE.value,
            torch_version=None,
        )
    if not main_path.exists():
        return ManagedEnvironmentValidationResult(
            success=False,
            detail="Managed workspace main.py is missing.",
            detected_backend="missing",
            detected_torch_channel=TorchReleaseChannel.STABLE.value,
            torch_version=None,
        )
    runtime_details = _query_runtime_details(workspace=workspace)
    detected_backend = _backend_from_runtime_details(runtime_details)
    torch_version = runtime_details.torch_version
    device_name = runtime_details.device_name
    detected_torch_channel = _channel_from_torch_version(torch_version).value
    probe_error = runtime_details.probe_error
    if probe_error is not None:
        return ManagedEnvironmentValidationResult(
            success=False,
            detail=f"Managed workspace torch runtime probe failed: {probe_error}",
            detected_backend=detected_backend,
            detected_torch_channel=detected_torch_channel,
            torch_version=torch_version,
            device_name=device_name,
        )
    if expected_accelerator is not AcceleratorClass.CPU and (
        detected_backend != expected_accelerator.value
    ):
        return ManagedEnvironmentValidationResult(
            success=False,
            detail=(
                "Managed workspace backend validation failed because the installed "
                f"backend resolved to `{detected_backend}` instead of "
                f"`{expected_accelerator.value}`."
            ),
            detected_backend=detected_backend,
            detected_torch_channel=detected_torch_channel,
            torch_version=torch_version,
            device_name=device_name,
        )
    if (
        expected_torch_channel is not None
        and detected_torch_channel != expected_torch_channel.value
    ):
        return ManagedEnvironmentValidationResult(
            success=False,
            detail=(
                "Managed workspace torch channel validation failed because the "
                f"installed channel resolved to `{detected_torch_channel}` instead of "
                f"`{expected_torch_channel.value}`."
            ),
            detected_backend=detected_backend,
            detected_torch_channel=detected_torch_channel,
            torch_version=torch_version,
            device_name=device_name,
        )
    if not runtime_details.device_operation:
        device_error = runtime_details.device_error
        detail = "Managed workspace torch device operation failed."
        if device_error is not None:
            detail = f"{detail} {device_error}"
        return ManagedEnvironmentValidationResult(
            success=False,
            detail=detail,
            detected_backend=detected_backend,
            detected_torch_channel=detected_torch_channel,
            torch_version=torch_version,
            device_name=device_name,
        )
    smoke_test = run_command(
        [str(python_executable), str(main_path), "--help"],
        cwd=workspace,
        check=False,
    )
    if smoke_test.returncode != 0:
        return ManagedEnvironmentValidationResult(
            success=False,
            detail=(
                "Managed workspace could not complete a ComfyUI launch smoke test."
            ),
            detected_backend=detected_backend,
            detected_torch_channel=detected_torch_channel,
            torch_version=torch_version,
            device_name=device_name,
        )
    if on_log is not None:
        on_log(
            app_text(
                "[Validation] torch=%1 backend=%2 channel=%3 device=%4",
                torch_version or "unknown",
                detected_backend,
                detected_torch_channel,
                device_name or "unknown",
            )
        )
    return ManagedEnvironmentValidationResult(
        success=True,
        detail="Managed workspace validation succeeded.",
        detected_backend=detected_backend,
        detected_torch_channel=detected_torch_channel,
        torch_version=torch_version,
        device_name=device_name,
    )


def _query_runtime_details(*, workspace: Path) -> TorchRuntimeDetails:
    """Return torch runtime details from the managed workspace interpreter."""

    return query_torch_runtime(
        python_executable=workspace_python_path(workspace),
        workspace=workspace,
        run_command=run_command,
    )


def _backend_from_runtime_details(details: TorchRuntimeDetails) -> str:
    """Return the normalized accelerator backend from queried torch details."""

    if details.hip:
        return AcceleratorClass.AMD.value
    if details.cuda:
        return AcceleratorClass.NVIDIA.value
    if details.xpu:
        return AcceleratorClass.INTEL_XPU.value
    if details.mps:
        return AcceleratorClass.APPLE_MPS.value
    return AcceleratorClass.CPU.value


def _channel_from_torch_version(torch_version: str | None) -> TorchReleaseChannel:
    """Infer the torch release channel from one normalized torch version string."""

    normalized = (torch_version or "").lower()
    if ".dev" in normalized or "nightly" in normalized:
        return TorchReleaseChannel.NIGHTLY
    return TorchReleaseChannel.STABLE


def run_command(
    command: list[str],
    *,
    cwd: Path,
    check: bool = True,
    timeout_seconds: float = 60,
) -> subprocess.CompletedProcess[str]:
    """Run one validator command and optionally require a zero exit code."""

    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"Validator command timed out after {timeout_seconds:g} seconds."
        ) from error
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Validator command failed with exit code {result.returncode}: {' '.join(command)}"
        )
    return result


__all__ = ["ManagedEnvironmentValidationResult", "validate_managed_environment"]
