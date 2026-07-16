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

"""Inspect and mutate acceleration packages in one managed workspace."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json
from pathlib import Path
from typing import Protocol

from substitute.infrastructure.comfy.managed_acceleration_policy import (
    ManagedAccelerationPackage,
    ManagedAccelerationRuntime,
)
from substitute.infrastructure.comfy.managed_install_commands import (
    pip_install,
    pip_uninstall,
)
from substitute.infrastructure.process.hidden_process_runner import run_command

_RUNTIME_PROBE = r"""
import json
import platform
import sys

import torch

capability = None
if torch.cuda.is_available():
    capability = list(torch.cuda.get_device_capability(0))

print(json.dumps({
    "python_version": platform.python_version(),
    "machine": platform.machine(),
    "torch_version": str(torch.__version__),
    "cuda_version": getattr(torch.version, "cuda", None),
    "hip_version": getattr(torch.version, "hip", None),
    "compute_capability": capability,
}))
"""

_DISTRIBUTION_PROBE = r"""
import importlib.metadata
import json
import sys

names = json.loads(sys.argv[1])
versions = {}
for name in names:
    try:
        versions[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        versions[name] = None
print(json.dumps(versions))
"""


class ManagedAccelerationEnvironment(Protocol):
    """Provide package operations required by acceleration reconciliation."""

    def installed_versions(
        self,
        distribution_names: tuple[str, ...],
    ) -> dict[str, str | None]:
        """Return installed versions for every requested distribution."""

    def install(self, package: ManagedAccelerationPackage) -> None:
        """Install one selected package artifact."""

    def verify(self, package: ManagedAccelerationPackage) -> tuple[bool, str]:
        """Return whether one package imports correctly in the workspace."""

    def uninstall(self, distribution_names: tuple[str, ...]) -> None:
        """Remove distributions that conflict with selected package ownership."""


class ManagedAccelerationWorkspace:
    """Adapt one managed workspace interpreter to acceleration operations."""

    def __init__(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        on_log: Callable[[str], None] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize the adapter without probing or mutating the environment."""

        self._workspace = workspace
        self._python_executable = python_executable
        self._on_log = on_log
        self._env = env

    def runtime(self) -> ManagedAccelerationRuntime:
        """Return normalized Python, Torch, and accelerator ABI details."""

        result = run_command(
            [str(self._python_executable), "-c", _RUNTIME_PROBE],
            cwd=self._workspace,
            check=False,
            env=self._env,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "runtime probe failed").strip()
            raise RuntimeError(
                "Managed acceleration runtime inspection failed: " + detail
            )
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "Managed acceleration runtime inspection returned invalid output."
            ) from error
        if not isinstance(payload, dict):
            raise RuntimeError(
                "Managed acceleration runtime inspection returned an invalid payload."
            )
        capability = _compute_capability(payload.get("compute_capability"))
        return ManagedAccelerationRuntime(
            python_version=_required_string(payload, "python_version"),
            machine=_required_string(payload, "machine"),
            torch_version=_required_string(payload, "torch_version"),
            cuda_version=_optional_string(payload.get("cuda_version")),
            hip_version=_optional_string(payload.get("hip_version")),
            compute_capability=capability,
        )

    def installed_versions(
        self,
        distribution_names: tuple[str, ...],
    ) -> dict[str, str | None]:
        """Return installed package versions through workspace import metadata."""

        result = run_command(
            [
                str(self._python_executable),
                "-c",
                _DISTRIBUTION_PROBE,
                json.dumps(distribution_names),
            ],
            cwd=self._workspace,
            check=False,
            env=self._env,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "package probe failed").strip()
            raise RuntimeError(
                "Managed acceleration package inspection failed: " + detail
            )
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "Managed acceleration package inspection returned invalid output."
            ) from error
        if not isinstance(payload, dict):
            raise RuntimeError(
                "Managed acceleration package inspection returned an invalid payload."
            )
        return {
            name: _optional_string(payload.get(name)) for name in distribution_names
        }

    def install(self, package: ManagedAccelerationPackage) -> None:
        """Install one checksum-pinned or bounded managed package requirement."""

        pip_install(
            self._python_executable,
            *package.install_arguments,
            on_log=self._on_log,
            env=self._env,
        )

    def uninstall(self, distribution_names: tuple[str, ...]) -> None:
        """Remove packages that conflict with the selected native runtime."""

        pip_uninstall(
            self._python_executable,
            *distribution_names,
            on_log=self._on_log,
            env=self._env,
        )

    def verify(self, package: ManagedAccelerationPackage) -> tuple[bool, str]:
        """Verify one package in a fresh workspace interpreter."""

        result = run_command(
            [str(self._python_executable), "-c", package.verification_code],
            cwd=self._workspace,
            check=False,
            env=self._env,
        )
        if result.returncode == 0:
            return True, "ready"
        detail = (result.stderr or result.stdout or "verification failed").strip()
        return False, detail


def _required_string(payload: dict[object, object], field: str) -> str:
    """Return one required non-empty probe string."""

    value = _optional_string(payload.get(field))
    if value is None:
        raise RuntimeError(f"Managed acceleration runtime omitted {field}.")
    return value


def _optional_string(value: object) -> str | None:
    """Normalize one optional string from subprocess JSON."""

    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _compute_capability(value: object) -> tuple[int, int] | None:
    """Normalize a two-component CUDA compute capability."""

    if not (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(component, int) for component in value)
    ):
        return None
    return int(value[0]), int(value[1])


__all__ = [
    "ManagedAccelerationEnvironment",
    "ManagedAccelerationWorkspace",
]
