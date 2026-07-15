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

"""Verify editor projection busy adapter behavior and boundaries."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.presentation.editor.panel.projection_busy_adapter import (
    EditorProjectionBusyAdapter,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUSY_ADAPTER_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_busy_adapter.py"
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


def test_projection_busy_adapter_starts_and_ends_panel_busy_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Busy adapter should call panel hooks and log projection context."""

    calls: list[tuple[str, object]] = []

    def begin_projection_busy(message: str = "Loading") -> str:
        """Record busy start and return the shell token."""

        calls.append(("begin", message))
        return "busy-token"

    def end_projection_busy(token: object) -> None:
        """Record busy end for the shell token."""

        calls.append(("end", token))

    panel = SimpleNamespace(
        _begin_projection_busy=begin_projection_busy,
        _end_projection_busy=end_projection_busy,
    )
    adapter = EditorProjectionBusyAdapter(panel)
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.editor.panel.projection_busy_adapter",
    )

    token = adapter.begin_projection_busy(
        workflow_id="workflow-a",
        pending_build_count=3,
    )
    adapter.end_projection_busy(
        token,
        workflow_id="workflow-a",
        busy_started=token is not None,
        pending_build_count=3,
    )

    assert token == "busy-token"
    assert calls == [("begin", "Loading"), ("end", "busy-token")]
    assert "Began editor projection busy state" in caplog.text
    assert "Ended editor projection busy state" in caplog.text
    assert "workflow_id=workflow-a" in caplog.text
    assert "pending_build_count=3" in caplog.text
    assert "busy_started=True" in caplog.text


def test_projection_busy_adapter_logs_without_panel_hooks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Missing optional busy hooks should not break staged projection cleanup."""

    adapter = EditorProjectionBusyAdapter(SimpleNamespace())
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.editor.panel.projection_busy_adapter",
    )

    token = adapter.begin_projection_busy(
        workflow_id="workflow-a",
        pending_build_count=1,
    )
    adapter.end_projection_busy(
        token,
        workflow_id="workflow-a",
        busy_started=token is not None,
        pending_build_count=1,
    )

    assert token is None
    assert "busy_started=False" in caplog.text


def test_projection_busy_adapter_does_not_import_qt_or_coordinator() -> None:
    """Busy adapter should stay binding-portable and out of the coordinator."""

    imports = _imported_module_names(BUSY_ADAPTER_SOURCE)

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def test_projection_coordinator_no_longer_defines_busy_methods() -> None:
    """Moved busy methods should not return to the coordinator monolith."""

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
    assert "EditorProjectionBusyAdapter" in composition_imported_names
    assert "_begin_projection_busy" not in coordinator_methods
    assert "_end_projection_busy" not in coordinator_methods
