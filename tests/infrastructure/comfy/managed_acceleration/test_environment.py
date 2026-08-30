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

"""Tests for managed acceleration workspace process adaptation."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from substitute.infrastructure.comfy import managed_acceleration_environment
from substitute.infrastructure.comfy.managed_acceleration_environment import (
    ManagedAccelerationWorkspace,
)
from substitute.infrastructure.comfy.managed_acceleration_policy import (
    ManagedAccelerationPackage,
    ManagedPackageVersion,
)


def test_workspace_adapter_probes_runtime_and_distribution_versions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The adapter should normalize runtime ABI facts through its workspace Python."""

    responses = iter(
        (
            {
                "python_version": "3.13.12",
                "machine": "AMD64",
                "torch_version": "2.10.0+cu130",
                "cuda_version": "13.0",
                "hip_version": None,
                "compute_capability": [12, 0],
            },
            {"transformers": "5.14.0", "sageattention": None},
        )
    )

    def fake_run_command(
        command: list[str],
        *,
        cwd: Path,
        check: bool,
        env: object | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Return sequential runtime and package probe payloads."""

        _ = command, cwd, check, env
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=json.dumps(next(responses)),
            stderr="",
        )

    monkeypatch.setattr(
        managed_acceleration_environment,
        "run_command",
        fake_run_command,
    )
    workspace = ManagedAccelerationWorkspace(
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
    )

    runtime = workspace.runtime()
    versions = workspace.installed_versions(("transformers", "sageattention"))

    assert runtime.compute_capability == (12, 0)
    assert runtime.cuda_version == "13.0"
    assert versions == {"transformers": "5.14.0", "sageattention": None}


def test_workspace_adapter_installs_exact_policy_arguments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The adapter should preserve checksum fragments and dependency isolation."""

    observed: list[tuple[str, ...]] = []

    def fake_pip_install(
        python_executable: Path,
        *packages: str,
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        """Record the exact pip arguments selected by policy."""

        _ = python_executable, on_log, env
        observed.append(packages)

    monkeypatch.setattr(
        managed_acceleration_environment,
        "pip_install",
        fake_pip_install,
    )
    workspace = ManagedAccelerationWorkspace(
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
    )
    package = ManagedAccelerationPackage(
        distribution_name="native-package",
        display_name="Native package",
        version=ManagedPackageVersion(exact_version="1.0"),
        install_arguments=(
            "--upgrade",
            "--no-deps",
            "https://example.test/native.whl#sha256=abc",
        ),
        verification_code="import native_package",
        required=False,
    )

    workspace.install(package)

    assert observed == [package.install_arguments]


def test_workspace_adapter_returns_actionable_verification_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Native import failures should retain subprocess diagnostics."""

    def fake_run_command(
        command: list[str],
        *,
        cwd: Path,
        check: bool,
        env: object | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Return one failed native import."""

        _ = cwd, check, env
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr="ImportError: DLL load failed",
        )

    monkeypatch.setattr(
        managed_acceleration_environment,
        "run_command",
        fake_run_command,
    )
    workspace = ManagedAccelerationWorkspace(
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
    )
    package = ManagedAccelerationPackage(
        distribution_name="native-package",
        display_name="Native package",
        version=ManagedPackageVersion(exact_version="1.0"),
        install_arguments=("native-package==1.0",),
        verification_code="import native_package",
        required=False,
    )

    ready, detail = workspace.verify(package)

    assert ready is False
    assert detail == "ImportError: DLL load failed"


def test_workspace_adapter_uninstalls_conflicting_distributions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Conflict cleanup should execute in the managed workspace interpreter."""

    observed: list[tuple[str, ...]] = []

    def fake_pip_uninstall(
        python_executable: Path,
        *packages: str,
        on_log: object | None = None,
        env: object | None = None,
    ) -> None:
        """Record selected package removals."""

        _ = python_executable, on_log, env
        observed.append(packages)

    monkeypatch.setattr(
        managed_acceleration_environment,
        "pip_uninstall",
        fake_pip_uninstall,
    )
    workspace = ManagedAccelerationWorkspace(
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
    )

    workspace.uninstall(("triton", "flash-attn-3"))

    assert observed == [("triton", "flash-attn-3")]
