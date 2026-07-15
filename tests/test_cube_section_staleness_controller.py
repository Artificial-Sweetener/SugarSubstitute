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

"""Verify cube-section staleness controller behavior and boundaries."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from substitute.presentation.editor.panel.cube_section_staleness_controller import (
    CubeSectionStalenessController,
)
from substitute.presentation.editor.panel.projection_build_registry import (
    CubeSectionBuildRegistry,
)
from substitute.presentation.editor.panel.projection_session import (
    ProjectionCompletionRegistry,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STALENESS_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "cube_section_staleness_controller.py"
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


def test_staleness_controller_adopts_visible_widget_before_marking_stale() -> None:
    """Visible widgets without build records should be adopted then marked stale."""

    widget = object()
    build_registry = CubeSectionBuildRegistry()
    controller = CubeSectionStalenessController(
        panel=SimpleNamespace(cube_widgets={"Cube": widget}),
        build_registry=build_registry,
        completion_registry=ProjectionCompletionRegistry(),
        workflow_context=SimpleNamespace(active_workflow_id=lambda: "workflow-a"),
    )

    assert not controller.mark_cube_sections_stale(
        ["Cube"],
        reason="node_definition_changed",
    )

    record = build_registry.record_for("Cube")
    assert record is not None
    assert record.widget is widget
    assert record.state == "stale"
    assert record.stale_reason == "node_definition_changed"


def test_staleness_controller_preserves_active_insert_completion_for_projection() -> (
    None
):
    """Active build tokens should mark node-definition insert completions superseded."""

    build_registry = CubeSectionBuildRegistry()
    completion_registry = ProjectionCompletionRegistry()
    token = build_registry.start(
        alias="Cube",
        widget=object(),
        session=object(),
        snapshot_identity=None,
        definition_identity=None,
    )
    completion_registry.register_pending_insert(
        workflow_id="workflow-a",
        cube_alias="Cube",
        token=token,
        completion_phase="complete",
        on_complete=lambda: None,
    )
    controller = CubeSectionStalenessController(
        panel=SimpleNamespace(cube_widgets={}),
        build_registry=build_registry,
        completion_registry=completion_registry,
        workflow_context=SimpleNamespace(active_workflow_id=lambda: "workflow-a"),
    )

    assert controller.mark_cube_sections_stale(
        ["Cube"],
        reason="node_definition_changed",
    )

    record = build_registry.record_for("Cube")
    assert record is not None
    assert record.state == "stale"
    completion = completion_registry.pending_insert_completions[
        completion_registry.pending_insert_key("workflow-a", "Cube")
    ]
    assert completion.token is token
    assert completion.superseded_reason == "node_definition_changed"


def test_staleness_controller_cancels_nontransferable_active_insert_completion() -> (
    None
):
    """Non node-definition stale reasons should cancel pending insert callbacks."""

    build_registry = CubeSectionBuildRegistry()
    completion_registry = ProjectionCompletionRegistry()
    token = build_registry.start(
        alias="Cube",
        widget=object(),
        session=object(),
        snapshot_identity=None,
        definition_identity=None,
    )
    completion_registry.register_pending_insert(
        workflow_id="workflow-a",
        cube_alias="Cube",
        token=token,
        completion_phase="complete",
        on_complete=lambda: None,
    )
    controller = CubeSectionStalenessController(
        panel=SimpleNamespace(cube_widgets={}),
        build_registry=build_registry,
        completion_registry=completion_registry,
        workflow_context=SimpleNamespace(active_workflow_id=lambda: "workflow-a"),
    )

    assert controller.mark_cube_sections_stale(["Cube"], reason="cube_removed")

    assert completion_registry.pending_insert_completions == {}


def test_cube_section_staleness_controller_does_not_import_qt_or_coordinator() -> None:
    """Staleness marking should stay Qt-free and coordinator-free."""

    imports = _imported_module_names(STALENESS_SOURCE)

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def test_projection_coordinator_delegates_cube_section_staleness() -> None:
    """The coordinator should keep only a public stale-marking facade."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    coordinator_class = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and node.name == "EditorPanelProjectionCoordinator"
    )
    method = next(
        node
        for node in coordinator_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "mark_cube_sections_stale"
    )

    assert any(
        isinstance(node, ast.Attribute) and node.attr == "cube_section_staleness"
        for node in ast.walk(method)
    )
    assert not any(
        isinstance(node, ast.Attribute)
        and node.attr == "mark_pending_insert_superseded"
        for node in ast.walk(method)
    )
