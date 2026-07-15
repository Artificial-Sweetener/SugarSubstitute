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

"""Verify editor projection workflow context behavior and boundaries."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from substitute.presentation.editor.panel.projection_workflow_context import (
    EditorProjectionWorkflowContext,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_CONTEXT_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_workflow_context.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
COMPOSITION_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_composition.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.panel.projection_coordinator",
)


def _imported_module_names(path: Path) -> set[str]:
    """Return all imported module names in a Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_workflow_context_reads_active_workflow_id_from_shell_session() -> None:
    """Workflow context should resolve the active workflow id from shell state."""

    panel = SimpleNamespace(
        mainwindow=SimpleNamespace(
            workflow_session_service=SimpleNamespace(
                active_workflow_id="workflow-a",
            )
        )
    )

    assert EditorProjectionWorkflowContext(panel).active_workflow_id() == "workflow-a"


def test_workflow_context_preserves_string_conversion_behavior() -> None:
    """Workflow context should preserve the coordinator's previous str conversion."""

    panel = SimpleNamespace(
        mainwindow=SimpleNamespace(
            workflow_session_service=SimpleNamespace(active_workflow_id=42)
        )
    )

    assert EditorProjectionWorkflowContext(panel).active_workflow_id() == "42"


def test_workflow_context_returns_empty_string_without_shell_session() -> None:
    """Missing shell context should keep the previous empty workflow id fallback."""

    assert EditorProjectionWorkflowContext(SimpleNamespace()).active_workflow_id() == ""


def test_projection_workflow_context_does_not_import_qt_or_coordinator() -> None:
    """Workflow context should stay binding-portable and out of the coordinator."""

    imports = _imported_module_names(WORKFLOW_CONTEXT_SOURCE)

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def test_projection_coordinator_no_longer_defines_workflow_context_method() -> None:
    """Moved workflow lookup should not return to the coordinator monolith."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    class_methods: dict[str, set[str]] = {}
    composition_tree = ast.parse(COMPOSITION_SOURCE.read_text(encoding="utf-8"))
    composition_imported_names = {
        alias.name
        for node in ast.walk(composition_tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods[node.name] = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }

    coordinator_methods = class_methods["EditorPanelProjectionCoordinator"]
    assert "EditorProjectionWorkflowContext" in composition_imported_names
    assert "_active_workflow_id" not in coordinator_methods
