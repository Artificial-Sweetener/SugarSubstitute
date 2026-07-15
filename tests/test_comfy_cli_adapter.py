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

"""Tests for Comfy CLI workspace adapter behavior."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
from typing import Any

import pytest

from substitute.infrastructure.comfy.comfy_cli_adapter import (
    ComfyCliWorkspaceAdapter,
)

_ADAPTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "comfy_cli_adapter.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.app",
    "subprocess",
    "urllib",
    "zipfile",
    "shutil",
)


def test_comfy_cli_adapter_imports_no_ui_archive_or_direct_process_boundaries() -> None:
    """Comfy CLI command construction must stay GUI-free and use the process runner."""

    source = _ADAPTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_comfy_cli_adapter_installs_cli_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Comfy CLI bootstrap should install into the selected workspace runtime."""

    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        _ = kwargs
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="")

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: object | None = None,
        timeout_seconds: int | None = None,
    ) -> int:
        _ = cwd, on_line, env, timeout_seconds
        commands.append(command)
        return 0

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_cli_adapter.run_command",
        fake_run,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_cli_adapter.stream_command",
        fake_stream,
    )
    adapter = ComfyCliWorkspaceAdapter(
        workspace=tmp_path,
        python_executable=tmp_path / ".venv" / "Scripts" / "python.exe",
    )

    adapter.ensure_available()

    assert commands == [
        [str(tmp_path / ".venv" / "Scripts" / "python.exe"), "-c", "import comfy_cli"],
        [
            str(tmp_path / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "pip",
            "install",
            "comfy-cli",
        ],
    ]


def test_comfy_cli_adapter_treats_manager_inspection_failure_as_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Registry lookup failures should allow source fallback instead of forcing install."""

    messages: list[str] = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        _ = kwargs
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="ComfyUI-Manager not found. 'cm-cli' command is not available.",
            stderr="",
        )

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_cli_adapter.run_command",
        fake_run,
    )
    adapter = ComfyCliWorkspaceAdapter(
        workspace=tmp_path,
        python_executable=tmp_path / ".venv" / "Scripts" / "python.exe",
        on_log=messages.append,
    )

    assert adapter.manager_knows_node("substitute-backend") is False
    assert messages == [
        "[ComfyNodepacks] Could not inspect Comfy Manager node list; using source fallback when available."
    ]


def test_comfy_cli_adapter_sets_manager_workspace_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Comfy Manager subprocesses should receive the selected ComfyUI path."""

    observed_env: dict[str, str] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        _ = command
        observed_env.update(kwargs["env"])
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_cli_adapter.run_command",
        fake_run,
    )
    adapter = ComfyCliWorkspaceAdapter(
        workspace=tmp_path,
        python_executable=tmp_path / ".venv" / "Scripts" / "python.exe",
        env={"EXISTING": "1"},
    )

    assert adapter.manager_knows_node("substitute-backend") is False
    assert observed_env["COMFYUI_PATH"] == str(tmp_path)
    assert observed_env["PYTHONUTF8"] == "1"
    assert observed_env["PYTHONIOENCODING"] == "utf-8:replace"
    assert observed_env["EXISTING"] == "1"


def test_comfy_cli_adapter_installs_nodes_through_manager_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Node installs should call Manager directly after Manager is provisioned."""

    commands: list[list[str]] = []

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: object | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[int, tuple[str, ...]]:
        _ = cwd, on_line, env, timeout_seconds
        commands.append(command)
        return 0, ("Installation was successful.",)

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_cli_adapter.stream_command_collecting_output",
        fake_stream,
    )
    adapter = ComfyCliWorkspaceAdapter(
        workspace=tmp_path,
        python_executable=tmp_path / ".venv" / "Scripts" / "python.exe",
    )

    adapter.install_node(
        "https://github.com/Artificial-Sweetener/Substitute-BackEnd.git"
    )

    assert commands == [
        [
            str(tmp_path / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "cm_cli",
            "install",
            "--exit-on-fail",
            "https://github.com/Artificial-Sweetener/Substitute-BackEnd.git",
        ]
    ]


def test_comfy_cli_adapter_treats_manager_error_output_as_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Manager install errors should fail even when the process exits zero."""

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: object | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[int, tuple[str, ...]]:
        _ = command, cwd, on_line, env, timeout_seconds
        return (
            0,
            (
                "ERROR: An error occurred while installing 'SimpleSyrup'.",
                "Node 'SimpleSyrup@unknown' not found in",
            ),
        )

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.comfy_cli_adapter.stream_command_collecting_output",
        fake_stream,
    )
    adapter = ComfyCliWorkspaceAdapter(
        workspace=tmp_path,
        python_executable=tmp_path / ".venv" / "Scripts" / "python.exe",
    )

    with pytest.raises(RuntimeError, match="SimpleSyrup@unknown"):
        adapter.install_node("SimpleSyrup")


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
