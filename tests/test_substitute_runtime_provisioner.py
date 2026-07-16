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

"""Tests for Substitute runtime provisioning and pip bootstrap repair."""

from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from substitute.domain.onboarding import (
    InstallationConfiguration,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.infrastructure.onboarding import SubstituteRuntimeProvisioner


def test_runtime_provisioner_bootstraps_missing_pip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Provisioning should repair an existing runtime venv that is missing pip."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime_configuration = RuntimeConfiguration.create_default(installation)
    python_executable = runtime_configuration.python_executable
    assert python_executable is not None
    python_executable.parent.mkdir(parents=True, exist_ok=True)
    python_executable.write_text("", encoding="utf-8")
    commands: list[list[str]] = []
    pip_version_checks = 0

    def _fake_run(
        command: list[str],
        *,
        check: bool,
        stdout: object | None = None,
        stderr: object | None = None,
    ) -> SimpleNamespace:
        nonlocal pip_version_checks
        _ = stdout, stderr
        commands.append(command)
        if command[1:] == ["-m", "pip", "--version"]:
            pip_version_checks += 1
            return SimpleNamespace(returncode=0 if pip_version_checks > 1 else 1)
        if command[1:] == ["-m", "ensurepip", "--upgrade"]:
            return SimpleNamespace(returncode=0)
        if command[1:5] == ["-m", "pip", "install", "--upgrade"]:
            return SimpleNamespace(returncode=0)
        if command[1:4] == ["-m", "pip", "install"]:
            return SimpleNamespace(returncode=0)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    provisioner = SubstituteRuntimeProvisioner(requirements_path=tmp_path / "reqs.txt")
    result = provisioner.provision(runtime_configuration)

    assert result.bootstrap_status is RuntimeBootstrapStatus.READY
    assert any(command[1:] == ["-m", "ensurepip", "--upgrade"] for command in commands)
    packaging_upgrade = next(
        command
        for command in commands
        if command[1:5] == ["-m", "pip", "install", "--upgrade"]
    )
    assert packaging_upgrade[5:] == ["pip", "setuptools"]


def test_runtime_provisioner_raises_clear_error_when_ensurepip_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Provisioning should fail with one clear message when pip bootstrap fails."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime_configuration = RuntimeConfiguration.create_default(installation)
    python_executable = runtime_configuration.python_executable
    assert python_executable is not None
    python_executable.parent.mkdir(parents=True, exist_ok=True)
    python_executable.write_text("", encoding="utf-8")

    def _fake_run(
        command: list[str],
        *,
        check: bool,
        stdout: object | None = None,
        stderr: object | None = None,
    ) -> SimpleNamespace:
        _ = stdout, stderr
        if command[1:] == ["-m", "pip", "--version"]:
            return SimpleNamespace(returncode=1)
        if command[1:] == ["-m", "ensurepip", "--upgrade"]:
            raise subprocess.CalledProcessError(1, command)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    provisioner = SubstituteRuntimeProvisioner(requirements_path=tmp_path / "reqs.txt")

    with pytest.raises(
        RuntimeError,
        match="Failed to bootstrap pip inside the Substitute runtime environment.",
    ):
        provisioner.provision(runtime_configuration)
