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

"""Tests for ready-shell launch gate ownership."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.app.bootstrap import ready_shell_launch_gate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
READY_SHELL_LAUNCH_GATE_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_launch_gate.py"
)
FORBIDDEN_READY_SHELL_GATE_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_ready_shell_launch_gate_starts_once_and_traces_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The launch gate should allow the first launch and remember that it started."""

    traces: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        ready_shell_launch_gate,
        "trace_mark",
        lambda name, **context: traces.append((name, context)),
    )
    state = ready_shell_launch_gate.ReadyShellLaunchGateState()

    allowed = ready_shell_launch_gate.try_begin_ready_shell_launch(
        state,
        startup_cancelled=False,
        shell_frame_present=False,
        no_comfy=False,
        target_mode="managed",
        target_host="127.0.0.1",
        target_port=8188,
    )

    assert allowed is True
    assert state.launch_started is True
    assert traces == [
        (
            "ready_shell.launch.enter",
            {
                "startup_cancelled": False,
                "ready_shell_launch_started": False,
                "shell_frame_present": False,
                "no_comfy": False,
                "target_mode": "managed",
                "target_host": "127.0.0.1",
                "target_port": 8188,
            },
        ),
    ]


def test_ready_shell_launch_gate_skips_cancelled_started_or_existing_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The launch gate should fail closed for duplicate or invalid launch attempts."""

    traces: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        ready_shell_launch_gate,
        "trace_mark",
        lambda name, **context: traces.append((name, context)),
    )
    state = ready_shell_launch_gate.ReadyShellLaunchGateState(launch_started=True)

    allowed = ready_shell_launch_gate.try_begin_ready_shell_launch(
        state,
        startup_cancelled=False,
        shell_frame_present=False,
        no_comfy=True,
        target_mode="remote",
        target_host="localhost",
        target_port=8188,
    )

    assert allowed is False
    assert state.launch_started is True
    assert traces[-1] == (
        "ready_shell.launch.skipped",
        {
            "startup_cancelled": False,
            "ready_shell_launch_started": True,
            "shell_frame_present": False,
        },
    )


def test_ready_shell_launch_gate_imports_no_forbidden_boundaries() -> None:
    """Ready-shell launch gating should remain free of concrete UI and IO adapters."""

    imported_modules = _imported_module_names(READY_SHELL_LAUNCH_GATE_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_READY_SHELL_GATE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_ready_shell_launch_gate() -> None:
    """Startup should not own ready-shell launch started state or skip tracing."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "run_startup_shell_flow(" in source
    assert "create_ready_shell_launch_controller(" not in source
    assert "ReadyShellLaunchController(" not in source
    assert "ReadyShellLaunchGateState()" not in source
    assert "try_begin_ready_shell_launch(" not in source
    assert "ready_shell_launch_started = False" not in source
    assert "ready_shell.launch.skipped" not in source
    assert "ready_shell.launch.enter" not in source


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
