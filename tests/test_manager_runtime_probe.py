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

"""Tests for non-mutating ComfyUI Manager runtime probes."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import subprocess
from typing import cast

import pytest

from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.infrastructure.comfy import manager_runtime_probe
from substitute.infrastructure.comfy.manager_contract import ComfyManagerContract


def test_integrated_manager_4_1_probe_requires_no_pygit2_api(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Manager 4.1 should validate through only its baseline package contract."""

    python = _prepare_integrated_workspace(tmp_path)
    observed_environment: dict[str, str] = {}

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        observed_environment.update(cast(Mapping[str, str], kwargs["env"]))
        assert "from comfyui_manager.common import git_compat" not in command[2]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "SUGARSUBSTITUTE_MANAGER_PROBE="
                '{"supports_pygit2": false, "version": "4.1"}\n'
            ),
            stderr="",
        )

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_runtime_probe.subprocess.run",
        fake_run,
    )

    result = manager_runtime_probe.ComfyManagerRuntimeProbe().integrated(
        workspace=tmp_path,
        python_executable=python,
        env={"PATH": "", "CM_USE_PYGIT2": "1"},
    )

    assert result.runtime is not None
    assert result.runtime.version == "4.1"
    assert result.runtime.supports_pygit2 is False
    assert result.runtime.uses_pygit2 is False
    assert "CM_USE_PYGIT2" not in observed_environment


def test_integrated_version_probe_ignores_manager_backend_banner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Only marker-prefixed JSON should determine the Manager version."""

    python = _prepare_integrated_workspace(tmp_path)
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_runtime_probe.subprocess.run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "[ComfyUI-Manager] Using Pygit2\n"
                "SUGARSUBSTITUTE_MANAGER_PROBE="
                '{"supports_pygit2": true, "version": "4.2.2"}\n'
            ),
            stderr="",
        ),
    )

    result = manager_runtime_probe.ComfyManagerRuntimeProbe().integrated(
        workspace=tmp_path,
        python_executable=python,
    )

    assert result.runtime is not None
    assert result.runtime.version == "4.2.2"
    assert result.runtime.supports_pygit2 is True


def test_pygit2_backend_probe_forces_backend_only_after_capability_detection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A capable Manager should receive the explicit pygit2 environment."""

    python = _prepare_integrated_workspace(tmp_path)
    baseline = manager_runtime_probe.ComfyManagerRuntimeProbe()
    runtime = _integrated_runtime(tmp_path, python)
    observed_environment: dict[str, str] = {}

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        observed_environment.update(cast(Mapping[str, str], kwargs["env"]))
        assert "git_compat.USE_PYGIT2" in command[2]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='SUGARSUBSTITUTE_MANAGER_PROBE={"uses_pygit2": true}\n',
            stderr="",
        )

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_runtime_probe.subprocess.run",
        fake_run,
    )

    result = baseline.pygit2_backend(runtime)

    assert result.runtime is not None
    assert result.runtime.uses_pygit2 is True
    assert observed_environment["CM_USE_PYGIT2"] == "1"


def test_legacy_probe_never_inherits_integrated_backend_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Legacy Manager should retain its own upstream Git behavior."""

    python = tmp_path / "python.exe"
    python.write_text("", encoding="utf-8")
    contract = ComfyManagerContract(tmp_path)
    contract.legacy_cli_path.parent.mkdir(parents=True)
    contract.legacy_cli_path.write_text("# fixture", encoding="utf-8")
    observed_environment: dict[str, str] = {}

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        observed_environment.update(cast(Mapping[str, str], kwargs["env"]))
        expected_creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        assert kwargs["creationflags"] == expected_creationflags
        return subprocess.CompletedProcess(command, 0, stdout="help", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.manager_runtime_probe.subprocess.run",
        fake_run,
    )

    result = manager_runtime_probe.ComfyManagerRuntimeProbe().legacy(
        workspace=tmp_path,
        python_executable=python,
        env={"PATH": "", "CM_USE_PYGIT2": "1"},
    )

    assert result.runtime is not None
    assert result.runtime.kind is ComfyManagerKind.LEGACY_CUSTOM_NODE
    assert "CM_USE_PYGIT2" not in observed_environment


def _prepare_integrated_workspace(workspace: Path) -> Path:
    """Create an integrated checkout contract and Python fixture."""

    (workspace / "comfy").mkdir(parents=True)
    (workspace / "comfy" / "cli_args.py").write_text(
        'parser.add_argument("--enable-manager")',
        encoding="utf-8",
    )
    (workspace / "manager_requirements.txt").write_text(
        "comfyui_manager==4.2.2",
        encoding="utf-8",
    )
    python = workspace / "python.exe"
    python.write_text("", encoding="utf-8")
    return python


def _integrated_runtime(
    workspace: Path,
    python: Path,
) -> ComfyManagerRuntime:
    """Build a pygit2-capable integrated runtime."""

    return ComfyManagerRuntime(
        kind=ComfyManagerKind.INTEGRATED,
        workspace=workspace,
        python_executable=python,
        version="4.2.2",
        supports_pygit2=True,
    )
