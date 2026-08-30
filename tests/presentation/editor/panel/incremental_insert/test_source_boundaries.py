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

"""Test incremental-insert source ownership and dependency boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[5]
PIPELINE_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "incremental_insert_pipeline.py"
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


def test_incremental_insert_pipeline_does_not_import_coordinator_or_fluent() -> None:
    """Incremental insert orchestration should stay out of the coordinator monolith."""

    imports = _imported_module_names(PIPELINE_SOURCE)
    source = PIPELINE_SOURCE.read_text(encoding="utf-8")

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )
    assert "_coordinator" not in source
    assert "EditorIncrementalInsertPorts(" in (
        PROJECT_ROOT
        / "substitute"
        / "presentation"
        / "editor"
        / "panel"
        / "projection_composition.py"
    ).read_text(encoding="utf-8")


def test_projection_coordinator_no_longer_defines_incremental_insert_pipeline() -> None:
    """Moved incremental insert methods should not return to the coordinator."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    class_methods: dict[str, set[str]] = {}
    coordinator_imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    composition_imported_names = {
        alias.name
        for node in ast.walk(ast.parse(COMPOSITION_SOURCE.read_text(encoding="utf-8")))
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
    assert "EditorHiddenBuildAndInsertPipeline" not in class_methods
    assert "EditorIncrementalInsertPipeline" not in coordinator_imported_names
    assert "EditorIncrementalInsertPipeline" in composition_imported_names
    assert "_log_insert_started" not in coordinator_methods
    assert "_prepare_incremental_insert_plan" not in coordinator_methods
    assert "_repopulate_incremental_insert_layout" not in coordinator_methods
    assert "_report_insert_complete" not in coordinator_methods
    assert "_finish_insert_first_usable" not in coordinator_methods
    assert "_finish_insert" not in coordinator_methods
    assert "_cancel_incremental_insert" not in coordinator_methods
