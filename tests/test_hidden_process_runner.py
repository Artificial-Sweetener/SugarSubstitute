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

"""Tests for hidden subprocess execution infrastructure."""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
import subprocess
from typing import Any

import pytest

from substitute.infrastructure.process import hidden_process_runner

_RUNNER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "process"
    / "hidden_process_runner.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy",
)


def test_hidden_process_runner_imports_no_ui_or_nodepack_boundaries() -> None:
    """Process execution infrastructure must stay generic and GUI-free."""

    source = _RUNNER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_run_command_uses_hidden_argument_list_options(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Captured commands should use argument lists and hidden process options."""

    observed: dict[str, object] = {}

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(
        "substitute.infrastructure.process.hidden_process_runner.subprocess.run",
        fake_run,
    )

    result = hidden_process_runner.run_command(
        ["python", "-m", "cm_cli", "clear"],
        cwd=tmp_path,
        check=True,
        env={"EXAMPLE": "1"},
    )

    assert result.stdout == "ok"
    assert observed["command"] == ["python", "-m", "cm_cli", "clear"]
    assert observed["cwd"] == str(tmp_path)
    assert observed["capture_output"] is True
    assert observed["text"] is True
    assert observed["encoding"] == "utf-8"
    assert observed["errors"] == "replace"
    assert observed["creationflags"] == hidden_process_runner.creation_flags()
    assert observed["env"] == {"EXAMPLE": "1"}
    assert observed["check"] is False


def test_stream_command_streams_only_nonblank_lines(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Streaming commands should forward nonblank merged output lines."""

    monkeypatch.setattr(
        "substitute.infrastructure.process.hidden_process_runner.subprocess.Popen",
        _fake_popen_factory(returncode=3, lines=("first\n", "\n", "second\n")),
    )
    emitted: list[str] = []

    exit_code = hidden_process_runner.stream_command(
        ["python", "-m", "pip", "install", "comfy-cli"],
        cwd=tmp_path,
        on_line=emitted.append,
        timeout_seconds=7,
    )

    assert exit_code == 3
    assert emitted == ["first", "second"]


def test_stream_command_collecting_output_retains_blank_lines(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Collecting commands should keep exact line records while streaming text."""

    monkeypatch.setattr(
        "substitute.infrastructure.process.hidden_process_runner.subprocess.Popen",
        _fake_popen_factory(returncode=4, lines=("first\n", "\n", "second\n")),
    )
    emitted: list[str] = []

    exit_code, output_lines = hidden_process_runner.stream_command_collecting_output(
        ["python", "-m", "cm_cli", "install", "SimpleSyrup"],
        cwd=tmp_path,
        on_line=emitted.append,
        timeout_seconds=7,
    )

    assert exit_code == 4
    assert output_lines == ("first", "", "second")
    assert emitted == ["first", "second"]


def test_run_command_check_raises_on_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Checked captured commands should surface failing exit codes."""

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        _ = kwargs
        return subprocess.CompletedProcess(command, 9, stdout="", stderr="bad")

    monkeypatch.setattr(
        "substitute.infrastructure.process.hidden_process_runner.subprocess.run",
        fake_run,
    )

    with pytest.raises(RuntimeError, match="exit code 9"):
        hidden_process_runner.run_command(
            ["python", "-m", "cm_cli"], cwd=tmp_path, check=True
        )


class _FakeStdout:
    """Minimal iterable stdout stream for subprocess tests."""

    def __init__(self, lines: Sequence[str]) -> None:
        """Store fake process output lines."""

        self._lines = lines
        self.closed = False

    def __iter__(self) -> Iterator[str]:
        """Iterate fake output lines."""

        return iter(self._lines)

    def close(self) -> None:
        """Record stream closure."""

        self.closed = True


class _FakeProcess:
    """Minimal Popen-compatible fake for process runner tests."""

    def __init__(self, *, returncode: int, lines: Sequence[str]) -> None:
        """Initialize fake return code and stdout."""

        self.returncode = returncode
        self.stdout = _FakeStdout(lines)
        self.wait_timeout: int | None = None

    def wait(self, timeout: int | None = None) -> int:
        """Record the timeout and return the fake exit code."""

        self.wait_timeout = timeout
        return self.returncode


def _fake_popen_factory(
    *,
    returncode: int,
    lines: Sequence[str],
) -> Callable[..., _FakeProcess]:
    """Build a Popen replacement that verifies hidden process options."""

    def fake_popen(
        command: list[str],
        **kwargs: Any,
    ) -> _FakeProcess:
        assert command
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.STDOUT
        assert kwargs["text"] is True
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"
        assert kwargs["creationflags"] == hidden_process_runner.creation_flags()
        return _FakeProcess(returncode=returncode, lines=lines)

    return fake_popen


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
