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

"""Verify ready-app process handoff launch behavior."""

from __future__ import annotations

import ast
import logging
from collections.abc import Sequence
from pathlib import Path
import subprocess
import sys

import pytest

from substitute.app.bootstrap.startup_process_launch import (
    launch_command_working_directory,
    start_ready_app_process,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
PROCESS_LAUNCH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_process_launch.py"
)
FORBIDDEN_PROCESS_LAUNCH_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.process_manager",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_launch_command_working_directory_uses_entrypoint_parent(
    tmp_path: Path,
) -> None:
    """Launch handoff should run from the app entrypoint directory when present."""

    entrypoint = tmp_path / "app" / "main.py"
    entrypoint.parent.mkdir()
    entrypoint.write_text("print('ready')", encoding="utf-8")

    assert launch_command_working_directory([sys.executable, str(entrypoint)]) == (
        entrypoint.parent
    )
    assert launch_command_working_directory([sys.executable]) is None
    assert (
        launch_command_working_directory([sys.executable, str(tmp_path / "missing.py")])
        is None
    )


def test_start_ready_app_process_launches_with_hidden_stdio(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ready-app handoff should detach stdio and use the entrypoint working directory."""

    entrypoint = tmp_path / "app" / "main.py"
    entrypoint.parent.mkdir()
    entrypoint.write_text("print('ready')", encoding="utf-8")
    observed: dict[str, object] = {}

    def _fake_popen(command: Sequence[str], **kwargs: object) -> object:
        """Record one launch command without starting a process."""

        observed["command"] = list(command)
        observed["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(
        "substitute.app.bootstrap.startup_process_launch.subprocess.Popen",
        _fake_popen,
    )

    assert start_ready_app_process([sys.executable, str(entrypoint), "--ready"]) is True

    assert observed["command"] == [sys.executable, str(entrypoint), "--ready"]
    kwargs = observed["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["cwd"] == entrypoint.parent
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert kwargs["close_fds"] is True
    if sys.platform == "win32":
        assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
        assert kwargs["startupinfo"] is not None


def test_start_ready_app_process_handles_empty_and_failed_commands(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """Failed launches should return false without logging full local command paths."""

    def _raise_os_error(_command: Sequence[str], **_kwargs: object) -> object:
        """Raise the broad process-launch failure handled by the launcher."""

        raise OSError("launch failed")

    monkeypatch.setattr(
        "substitute.app.bootstrap.startup_process_launch.subprocess.Popen",
        _raise_os_error,
    )

    assert start_ready_app_process([]) is False
    with caplog.at_level(logging.ERROR):
        assert (
            start_ready_app_process(
                [sys.executable, str(tmp_path / "app" / "main.py"), "--ready"]
            )
            is False
        )

    assert "Failed to start fresh app process" in caplog.text
    assert str(tmp_path) not in caplog.text


def test_process_launch_imports_only_runtime_launch_boundaries() -> None:
    """Process launch may own subprocess but must stay out of Qt and presentation."""

    imported_modules = _imported_module_names(PROCESS_LAUNCH_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_PROCESS_LAUNCH_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()
    assert "subprocess" in imported_modules


def test_startup_facade_no_longer_imports_subprocess() -> None:
    """The startup facade should delegate ready-app handoff process launches."""

    assert "subprocess" not in _imported_module_names(STARTUP_SOURCE)
