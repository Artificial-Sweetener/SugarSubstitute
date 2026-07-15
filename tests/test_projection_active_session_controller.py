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

"""Verify active projection session controller behavior and boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.presentation.editor.panel.projection_active_session_controller import (
    EditorActiveProjectionSessionController,
)
from substitute.presentation.editor.panel.projection_session import (
    ActiveProjectionSessionRegistry,
    ProjectionCompletionRegistry,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_active_session_controller.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.panel.projection_coordinator",
)


def _imported_module_names(path: Path) -> set[str]:
    """Return all imported module names in one Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_active_projection_session_controller_resolves_session_callbacks() -> None:
    """Successful session resolution should invoke claimed projection callbacks."""

    sessions = ActiveProjectionSessionRegistry()
    completions = ProjectionCompletionRegistry()
    discarded: list[str] = []
    completed: list[str] = []
    controller = EditorActiveProjectionSessionController(
        sessions=sessions,
        completions=completions,
        discard_pending_visible_commit=discarded.append,
    )

    session = controller.start(
        workflow_id="workflow-a",
        cube_entries=[("Cube", object())],
    )
    completions.register_projection_completion(
        session,
        workflow_id="workflow-a",
        aliases={"Cube"},
        on_complete=lambda: completed.append("projection"),
        reason="test",
    )
    controller.resolve(session, reason="complete")
    controller.resolve(session, reason="complete_again")

    assert discarded == ["superseded_by_new_full_projection"]
    assert completed == ["projection"]
    assert controller.active_session is None


def test_active_projection_session_controller_transfers_superseded_callbacks() -> None:
    """Replacement sessions should inherit callbacks for still-owned aliases."""

    sessions = ActiveProjectionSessionRegistry()
    completions = ProjectionCompletionRegistry()
    controller = EditorActiveProjectionSessionController(
        sessions=sessions,
        completions=completions,
        discard_pending_visible_commit=lambda _reason: None,
    )
    completed: list[str] = []

    first = controller.start(
        workflow_id="workflow-a",
        cube_entries=[("A", object()), ("B", object())],
    )
    completions.register_projection_completion(
        first,
        workflow_id="workflow-a",
        aliases={"A"},
        on_complete=lambda: completed.append("projection-a"),
        reason="test",
    )
    completions.register_projection_completion(
        first,
        workflow_id="workflow-a",
        aliases={"B"},
        on_complete=lambda: completed.append("projection-b"),
        reason="test",
    )

    replacement = controller.start(
        workflow_id="workflow-a",
        cube_entries=[("A", object())],
    )
    controller.resolve(replacement, reason="replacement_complete")

    assert replacement.projection_completions == [first.projection_completions[0]]
    assert first.projection_completions[1].resolved
    assert completed == ["projection-a"]


def test_active_projection_session_controller_does_not_import_qt_or_coordinator() -> (
    None
):
    """Active session orchestration should stay Qt-free and coordinator-free."""

    imports = _imported_module_names(CONTROLLER_SOURCE)

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def test_projection_coordinator_no_longer_defines_active_session_wrappers() -> None:
    """Active session lifecycle should not return to the coordinator monolith."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    class_methods: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods[node.name] = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }

    coordinator_methods = class_methods["EditorPanelProjectionCoordinator"]
    removed_wrappers = {
        "_start_active_projection_session",
        "_supersede_active_projection_session",
        "_active_projection_session_owns",
        "_clear_active_projection_session",
        "_log_active_projection_session_cleared",
        "_resolve_active_projection_session",
        "_cancel_active_projection_session",
        "_resolve_active_projection_session_callbacks",
        "_cancel_active_projection_session_callbacks",
        "_visible_commits_discard_pending_visible_projection_commit",
        "_active_projection_session",
    }
    assert coordinator_methods.isdisjoint(removed_wrappers)
