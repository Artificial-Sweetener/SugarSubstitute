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

"""Tests for prompt-safe visible startup summary calculation."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from substitute.app.bootstrap.startup_summary import (
    StartupVisibleLoadingSummary,
    build_visible_loading_summary,
)
from substitute.app.bootstrap.startup_timing import StartupTimer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUMMARY_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_summary.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_SUMMARY_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_visible_loading_summary_counts_restored_workspace() -> None:
    """Summary should expose restored workflow count and active cube count."""

    timer = _marked_timer()
    workspace = SimpleNamespace(
        active_workflow_id="wf-b",
        workflows=(
            SimpleNamespace(
                workflow_id="wf-a",
                workflow=SimpleNamespace(cubes={"a": object()}),
            ),
            SimpleNamespace(
                workflow_id="wf-b",
                workflow=SimpleNamespace(cubes={"a": object(), "b": object()}),
            ),
        ),
    )

    summary = build_visible_loading_summary(
        startup_timer=timer,
        workspace=workspace,
    )

    assert summary == StartupVisibleLoadingSummary(
        session_restore_used=True,
        workflow_count=2,
        active_cube_count=2,
        splash_close_to_shell_show_ms="50.000",
        splash_close_to_hydration_complete_ms="150.000",
        splash_close_to_restore_running_ms="200.000",
    )
    assert summary.log_fields() == {
        "session_restore_used": True,
        "workflow_count": 2,
        "active_cube_count": 2,
        "splash_close_to_shell_show_ms": "50.000",
        "splash_close_to_hydration_complete_ms": "150.000",
        "splash_close_to_restore_running_ms": "200.000",
    }


def test_visible_loading_summary_handles_missing_restore_data() -> None:
    """Summary should stay bounded when restore data or milestones are absent."""

    timer = StartupTimer(clock=lambda: 0.0)
    workspace = SimpleNamespace(active_workflow_id="wf-a", workflows=["not", "tuple"])

    summary = build_visible_loading_summary(
        startup_timer=timer,
        workspace=workspace,
    )

    assert summary.session_restore_used is True
    assert summary.workflow_count == 0
    assert summary.active_cube_count == 0
    assert summary.splash_close_to_shell_show_ms == ""
    assert summary.splash_close_to_hydration_complete_ms == ""
    assert summary.splash_close_to_restore_running_ms == ""


def test_startup_summary_imports_no_forbidden_boundaries() -> None:
    """Startup summary calculation should stay free of Qt and infrastructure."""

    imported_modules = _imported_module_names(SUMMARY_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_SUMMARY_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_formats_visible_summary_fields() -> None:
    """The startup facade should delegate visible summary field calculation."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    assert "def _format_optional_elapsed" not in source
    assert "build_visible_loading_summary(" not in source
    assert "managed_ready_launch.create_post_show_controller(" in launch_source
    assert "managed_ready_runtime.create_post_show_controller(" not in source
    assert "create_bound_ready_shell_post_show_controller(" not in source
    assert "create_ready_shell_post_show_controller(" not in source
    assert "ReadyShellPostShowController(" not in source
    assert "emit_ready_shell_visible_startup_summary(" not in source
    assert "emit_visible_startup_summary(" not in source


def _marked_timer() -> StartupTimer:
    """Build a startup timer with deterministic visible-summary milestones."""

    ticks = iter((0.0, 0.100, 0.150, 0.250, 0.300))
    timer = StartupTimer(clock=lambda: next(ticks))
    timer.mark("splash_closed")
    timer.mark("main_shell_shown")
    timer.mark("hydration_completed")
    timer.mark("restore_lifecycle_running")
    return timer


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
