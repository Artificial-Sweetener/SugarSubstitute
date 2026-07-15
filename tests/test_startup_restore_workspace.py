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

"""Tests for restored workspace facts used during startup."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from substitute.app.bootstrap.startup_restore_workspace import (
    restored_active_workflow_cube_count,
    restored_active_workflow_id,
    restored_workspace_workflow_count,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESTORE_WORKSPACE_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_restore_workspace.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_RESTORE_WORKSPACE_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_restored_workspace_facts_read_valid_snapshot_shape() -> None:
    """Restored workspace helpers should expose bounded startup facts."""

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

    assert restored_workspace_workflow_count(workspace) == 2
    assert restored_active_workflow_id(workspace) == "wf-b"
    assert restored_active_workflow_cube_count(workspace) == 2


def test_restored_workspace_facts_handle_missing_or_invalid_shapes() -> None:
    """Restored workspace helpers should not trust malformed snapshot attributes."""

    assert restored_workspace_workflow_count(None) == 0
    assert restored_active_workflow_id(None) == ""
    assert restored_active_workflow_cube_count(None) == 0

    malformed = SimpleNamespace(active_workflow_id=object(), workflows=["wf-a"])

    assert restored_workspace_workflow_count(malformed) == 0
    assert restored_active_workflow_id(malformed) == ""
    assert restored_active_workflow_cube_count(malformed) == 0


def test_startup_restore_workspace_imports_no_forbidden_boundaries() -> None:
    """Restored workspace facts should stay free of Qt and infrastructure."""

    imported_modules = _imported_module_names(RESTORE_WORKSPACE_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_RESTORE_WORKSPACE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_restored_workspace_facts() -> None:
    """The startup facade should not own restored workspace snapshot helpers."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    assert "def _workspace_workflow_count" not in source
    assert "def _restored_active_workflow_id" not in source
    assert "managed_ready_runtime.restored_workspace_workflow_count" not in source
    assert "managed_ready_runtime.restored_active_workflow_id" not in source
    assert (
        "managed_ready_launch.create_initial_workspace_prehydration_task("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_initial_workspace_prehydration_task" not in source
    )
    assert "managed_ready_launch.create_show_gate_task(" in launch_source
    assert "managed_ready_runtime.create_show_gate_task" not in source
    assert "workspace_workflow_count=restored_workspace_workflow_count" not in source
    assert "fallback_workflow_id=lambda: restored_active_workflow_id" not in source
    assert (
        "from substitute.app.bootstrap.startup_restore_workspace import" not in source
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
