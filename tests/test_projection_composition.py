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

"""Verify editor projection collaborator composition ownership."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from substitute.presentation.editor.panel.clean_projection_refresh import (
    EditorCleanProjectionRefreshController,
)
from substitute.presentation.editor.panel.cube_section_build_controller import (
    CubeSectionBuildController,
)
from substitute.presentation.editor.panel.cube_section_staleness_controller import (
    CubeSectionStalenessController,
)
from substitute.presentation.editor.panel.full_projection_load_pipeline import (
    EditorFullProjectionLoadPipeline,
)
from substitute.presentation.editor.panel.hidden_build_scheduler import (
    HiddenBuildScheduler,
)
from substitute.presentation.editor.panel.incremental_insert_pipeline import (
    EditorIncrementalInsertPipeline,
)
from substitute.presentation.editor.panel.projected_widget_builder import (
    ProjectedWidgetBuilder,
)
from substitute.presentation.editor.panel.projection_active_session_controller import (
    EditorActiveProjectionSessionController,
)
from substitute.presentation.editor.panel.projection_build_registry import (
    CubeSectionBuildRegistry,
)
from substitute.presentation.editor.panel.projection_busy_adapter import (
    EditorProjectionBusyAdapter,
)
from substitute.presentation.editor.panel.projection_composition import (
    EditorProjectionCoordinatorPort,
    EditorProjectionComposition,
    compose_editor_projection,
)
from substitute.presentation.editor.panel.projection_lifecycle import (
    EditorProjectionLifecyclePipeline,
    EditorProjectionRuntimeIssueIntegration,
)
from substitute.presentation.editor.panel.projection_ports import (
    EditorRefreshPanelProtocol,
)
from substitute.presentation.editor.panel.projection_preparation import (
    EditorProjectionPreparationController,
)
from substitute.presentation.editor.panel.projection_session import (
    ActiveProjectionSessionRegistry,
    ProjectionCompletionRegistry,
    ProjectionSurfaceStateController,
)
from substitute.presentation.editor.panel.projection_workflow_context import (
    EditorProjectionWorkflowContext,
)
from substitute.presentation.editor.panel.rendering.render_reconciler import (
    EditorPanelRenderReconciler,
)
from substitute.presentation.editor.panel.runtime_issue_projection_adapter import (
    RuntimeIssueProjectionAdapter,
)
from substitute.presentation.editor.panel.visible_projection_commit import (
    EditorVisibleProjectionCommitPipeline,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPOSITION_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_composition.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
FORBIDDEN_COMPOSITION_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.panel.projection_coordinator",
)
COORDINATOR_ALIAS_NAMES = (
    "_build_registry",
    "_projection_completions",
    "_projection_sessions",
    "_active_sessions",
    "_projection_state",
    "_runtime_issues",
    "_projection_preparation",
    "_render_reconciler",
    "_workflow_context",
    "_projection_busy",
    "_clean_projection_refresh",
    "_cube_section_staleness",
    "_runtime_issue_projection",
    "_incremental_inserts",
    "_projected_widget_builder",
    "_hidden_build_scheduler",
    "_cube_section_builds",
    "_visible_commits",
    "_projection_lifecycle",
    "_full_projection_loads",
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


class _Panel:
    """Provide passive panel attributes required for construction."""

    def __init__(self) -> None:
        """Create the shell/workflow state collaborators read by adapters."""

        self.mainwindow = SimpleNamespace(
            workflow_session_service=SimpleNamespace(active_workflow_id="workflow-a")
        )
        self._projection_dirty = False
        self._projection_signature = None

    def isVisible(self) -> bool:  # noqa: N802
        """Report a visible panel for visible-commit ports."""

        return True

    def _build_error_cube_widget(self, cube_alias: str, cube_state: object) -> object:
        """Build one passive runtime issue widget."""

        return (cube_alias, cube_state)


class _Coordinator:
    """Record invalidation calls made through lifecycle ports."""

    def __init__(self) -> None:
        """Create empty invalidation storage."""

        self.invalidations: list[str] = []

    def invalidate_projection(self, *, reason: str) -> None:
        """Record one projection invalidation."""

        self.invalidations.append(reason)


def test_compose_editor_projection_builds_projection_collaborators() -> None:
    """Projection construction should live in the composition owner."""

    panel = cast(EditorRefreshPanelProtocol, _Panel())
    coordinator = cast(EditorProjectionCoordinatorPort, _Coordinator())

    composition = compose_editor_projection(panel, coordinator)

    assert isinstance(composition.build_registry, CubeSectionBuildRegistry)
    assert isinstance(composition.projection_completions, ProjectionCompletionRegistry)
    assert isinstance(composition.projection_sessions, ActiveProjectionSessionRegistry)
    assert isinstance(
        composition.active_sessions,
        EditorActiveProjectionSessionController,
    )
    assert isinstance(composition.projection_state, ProjectionSurfaceStateController)
    assert isinstance(
        composition.runtime_issues,
        EditorProjectionRuntimeIssueIntegration,
    )
    assert isinstance(
        composition.projection_preparation,
        EditorProjectionPreparationController,
    )
    assert isinstance(composition.render_reconciler, EditorPanelRenderReconciler)
    assert isinstance(composition.workflow_context, EditorProjectionWorkflowContext)
    assert isinstance(composition.projection_busy, EditorProjectionBusyAdapter)
    assert isinstance(
        composition.clean_projection_refresh,
        EditorCleanProjectionRefreshController,
    )
    assert isinstance(
        composition.cube_section_staleness,
        CubeSectionStalenessController,
    )
    assert isinstance(
        composition.runtime_issue_projection, RuntimeIssueProjectionAdapter
    )
    assert isinstance(composition.incremental_inserts, EditorIncrementalInsertPipeline)
    assert isinstance(composition.projected_widget_builder, ProjectedWidgetBuilder)
    assert isinstance(composition.hidden_build_scheduler, HiddenBuildScheduler)
    assert isinstance(composition.cube_section_builds, CubeSectionBuildController)
    assert isinstance(
        composition.visible_commits,
        EditorVisibleProjectionCommitPipeline,
    )
    assert isinstance(
        composition.projection_lifecycle,
        EditorProjectionLifecyclePipeline,
    )
    assert isinstance(
        composition.full_projection_loads, EditorFullProjectionLoadPipeline
    )


def test_projection_composition_does_not_import_coordinator_or_fluent() -> None:
    """Projection composition should not depend back on the coordinator monolith."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(COMPOSITION_SOURCE)
            if imported_module.startswith(FORBIDDEN_COMPOSITION_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()


def test_projection_coordinator_delegates_collaborator_construction() -> None:
    """Projection coordinator should call the composer instead of owning construction."""

    source = COORDINATOR_SOURCE.read_text(encoding="utf-8")

    assert "EditorProjectionComposition" in source
    assert "self._composition: EditorProjectionComposition" in source
    assert "compose_editor_projection(" in source
    assert "panel," in source
    assert "self," in source
    assert "CubeSectionBuildRegistry(" not in source
    assert "EditorProjectionPreparationController(" not in source
    assert "EditorVisibleProjectionCommitPipeline(" not in source
    assert "EditorProjectionLifecyclePipeline(" not in source


def test_projection_composition_exports_typed_bundle() -> None:
    """Projection composer should return the typed collaborator bundle."""

    assert callable(EditorProjectionComposition)


def test_projection_coordinator_does_not_store_collaborator_aliases() -> None:
    """Projection coordinator should expose only the typed composition bundle."""

    source = COORDINATOR_SOURCE.read_text(encoding="utf-8")

    for alias_name in COORDINATOR_ALIAS_NAMES:
        assert f"self.{alias_name}" not in source
