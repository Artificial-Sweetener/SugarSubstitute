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

"""Tests for exact-version Comfy Registry nodepack installation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from substitute.application.comfy_nodepacks.core_nodepack_reconciliation_plan import (
    RegistryInstallOutcome,
)
from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.infrastructure.comfy.nodepack_manifest import CORE_COMFY_NODEPACKS
from substitute.infrastructure.comfy.nodepack_registry_installer import (
    ComfyNodepackRegistryInstaller,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path


def test_integrated_cli_installs_exact_registry_release_without_manager_deps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Invoke Comfy-owned CNR acquisition while retaining dependency ownership."""

    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_runtime.ComfyManagerCommandRunner._module_available",
        lambda self, module_name: True,
    )

    def fake_stream(command: list[str], **kwargs: Any) -> tuple[int, tuple[str, ...]]:
        """Capture the complete Registry process contract."""

        observed["command"] = command
        observed.update(kwargs)
        return 0, ("[INSTALLED] substitute-backend [1.9.1]",)

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_runtime.stream_command_collecting_output",
        fake_stream,
    )

    result = ComfyNodepackRegistryInstaller().install_exact(
        manager_runtime=_runtime(tmp_path, python),
        nodepack=CORE_COMFY_NODEPACKS[0],
        on_log=None,
        env={"VIRTUAL_ENV": "wrong", "CONDA_PREFIX": "also-wrong"},
    )

    assert result.outcome is RegistryInstallOutcome.INSTALLED
    assert observed["command"] == [
        subprocess_path(python),
        "-m",
        "comfy_cli",
        "--workspace",
        subprocess_path(tmp_path),
        "--skip-prompt",
        "node",
        "install",
        "--exit-on-fail",
        "--no-deps",
        "substitute-backend@1.9.1",
        "--mode",
        "remote",
    ]
    selected_env = observed["env"]
    assert isinstance(selected_env, dict)
    assert selected_env["VIRTUAL_ENV"] == str(python.parent.parent)
    assert selected_env["COMFYUI_PATH"] == str(tmp_path.resolve())
    assert selected_env["COMFYUI_FOLDERS_BASE_PATH"] == str(tmp_path.resolve())
    assert selected_env["GIT_PYTHON_REFRESH"] == "quiet"
    assert "CONDA_PREFIX" not in selected_env


def test_integrated_manager_module_is_used_when_comfy_cli_is_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Support existing Comfy installs that expose Manager without comfy-cli."""

    probe_results = iter((False, True))
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_runtime.ComfyManagerCommandRunner._module_available",
        lambda self, module_name: next(probe_results),
    )
    observed: list[str] = []

    def fake_stream(
        command: list[str],
        **kwargs: Any,
    ) -> tuple[int, tuple[str, ...]]:
        """Capture the direct Manager command."""

        _ = kwargs
        observed.extend(command)
        return 0, ("[INSTALLED] substitute-backend [1.9.1]",)

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_runtime.stream_command_collecting_output",
        fake_stream,
    )

    result = ComfyNodepackRegistryInstaller().install_exact(
        manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
        nodepack=CORE_COMFY_NODEPACKS[0],
        on_log=None,
        env={},
    )

    assert result.outcome is RegistryInstallOutcome.INSTALLED
    assert observed[1:5] == ["-m", "cm_cli", "install", "--exit-on-fail"]


@pytest.mark.parametrize(
    ("output", "expected"),
    (
        (
            ("[   SKIP  ] node => Already installed",),
            RegistryInstallOutcome.ALREADY_INSTALLED,
        ),
        (
            ("Installation reserved: substitute-backend",),
            RegistryInstallOutcome.PENDING_STARTUP,
        ),
        (("Available version of 'node'",), RegistryInstallOutcome.VERSION_UNAVAILABLE),
        (
            ("Cannot connect to ComfyRegistry",),
            RegistryInstallOutcome.REGISTRY_UNREACHABLE,
        ),
        (("unexpected manager failure",), RegistryInstallOutcome.FAILED),
    ),
)
def test_registry_failures_are_classified_for_safe_fallback_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    output: tuple[str, ...],
    expected: RegistryInstallOutcome,
) -> None:
    """Distinguish availability failures from arbitrary Manager failures."""

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_runtime.ComfyManagerCommandRunner._module_available",
        lambda self, module_name: True,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_runtime.stream_command_collecting_output",
        lambda *args, **kwargs: (
            0 if expected is RegistryInstallOutcome.PENDING_STARTUP else 1,
            output,
        ),
    )

    result = ComfyNodepackRegistryInstaller().install_exact(
        manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
        nodepack=CORE_COMFY_NODEPACKS[0],
        on_log=None,
        env={},
    )

    assert result.outcome is expected


def test_missing_manager_cli_is_an_availability_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Allow pinned fallback when an existing Comfy lacks callable Manager tooling."""

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_runtime.ComfyManagerCommandRunner._module_available",
        lambda self, module_name: False,
    )

    result = ComfyNodepackRegistryInstaller().install_exact(
        manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
        nodepack=CORE_COMFY_NODEPACKS[0],
        on_log=None,
        env={},
    )

    assert result.outcome is RegistryInstallOutcome.REGISTRY_UNREACHABLE


def test_unknown_registry_failure_is_written_to_durable_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Retain bounded Manager output when an unknown failure needs fallback."""

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_runtime.ComfyManagerCommandRunner._module_available",
        lambda self, module_name: True,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_manager_runtime.stream_command_collecting_output",
        lambda *args, **kwargs: (1, ("first detail", "final manager failure")),
    )

    result = ComfyNodepackRegistryInstaller().install_exact(
        manager_runtime=_runtime(tmp_path, tmp_path / "python.exe"),
        nodepack=CORE_COMFY_NODEPACKS[0],
        on_log=None,
        env={},
    )

    assert result.outcome is RegistryInstallOutcome.FAILED
    assert "exit_code=1" in caplog.text
    assert "output_tail=first detail | final manager failure" in caplog.text


def _runtime(workspace: Path, python: Path) -> ComfyManagerRuntime:
    """Build one validated integrated Manager runtime fixture."""

    return ComfyManagerRuntime(
        kind=ComfyManagerKind.INTEGRATED,
        workspace=workspace,
        python_executable=python,
        version="4.1",
    )
