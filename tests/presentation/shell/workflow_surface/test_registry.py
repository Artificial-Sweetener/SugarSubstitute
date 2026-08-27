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

"""Contract tests for workflow surface topology and lifecycle classification."""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from pathlib import Path

from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import WorkflowState
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceInvalidationService,
)
from substitute.presentation.shell.workflow_surface_registry import (
    WorkflowSurfaceLifecycleState,
    WorkflowSurfaceOwnership,
    WorkflowSurfaceRegistry,
)


class _ProjectionAwareEditorPanel:
    """Editor-panel double exposing projection-cleanliness APIs."""

    def __init__(self, *, clean: bool) -> None:
        """Store the cleanliness response."""

        self._clean = clean

    def current_projection_signature(
        self,
        *,
        workflow_id: str,
        cube_entries: list[tuple[str, object]],
        cube_states: Mapping[str, object],
        stack_order: list[str],
    ) -> object:
        """Return a deterministic projection signature."""

        return (
            workflow_id,
            tuple(cube_entries),
            tuple(cube_states),
            tuple(stack_order),
        )

    def is_projection_clean(self, signature: object) -> bool:
        """Return the configured cleanliness state."""

        return signature is not None and self._clean


def test_registry_classifies_surface_ownership() -> None:
    """Surface descriptors should encode cached versus shared route topology."""

    registry = WorkflowSurfaceRegistry(
        editor_panels={},
        cube_stacks={},
        override_managers={},
        workflows={},
    )

    assert (
        registry.descriptor(WorkflowSurface.EDITOR).ownership
        == WorkflowSurfaceOwnership.PER_WORKFLOW_CACHED
    )
    assert (
        registry.descriptor(WorkflowSurface.CANVAS).ownership
        == WorkflowSurfaceOwnership.SHARED_ROUTE_PROJECTED
    )
    assert (
        registry.descriptor(WorkflowSurface.GENERATION_AVAILABILITY).ownership
        == WorkflowSurfaceOwnership.SHARED_ROUTE_PROJECTED
    )


def test_registry_returns_existing_cached_surfaces_without_materializing() -> None:
    """Registry accessors should return existing surface objects only."""

    editor = object()
    cube_stack = object()
    manager = object()
    registry = WorkflowSurfaceRegistry(
        editor_panels={"wf-a": editor},
        cube_stacks={"wf-a": cube_stack},
        override_managers={"wf-a": manager},
        workflows={},
    )

    assert registry.editor_panel("wf-a") is editor
    assert registry.cube_stack("wf-a") is cube_stack
    assert registry.override_manager("wf-a") is manager
    assert registry.editor_panel("missing") is None
    assert not registry.workflow_ui_materialized("missing")


def test_registry_treats_direct_editor_without_stack_as_fully_materialized() -> None:
    """Document topology should not require a phantom cube stack for direct JSON."""

    workflow = WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=Path("workflow.json"),
            source_workflow={"nodes": []},
            buffer={"nodes": {}},
        )
    )
    registry = WorkflowSurfaceRegistry(
        editor_panels={"wf-direct": object()},
        cube_stacks={},
        override_managers={"wf-direct": object()},
        workflows={"wf-direct": workflow},
    )

    assert registry.workflow_ui_materialized("wf-direct")


def test_registry_distinguishes_unprojected_editor_from_clean_editor() -> None:
    """Editor lifecycle should use the editor panel's projection proof."""

    workflow = SimpleNamespace(cubes={"CubeA": object()}, stack_order=["CubeA"])
    registry = WorkflowSurfaceRegistry(
        editor_panels={"wf-a": _ProjectionAwareEditorPanel(clean=False)},
        cube_stacks={"wf-a": object()},
        override_managers={"wf-a": object()},
        workflows={"wf-a": workflow},
    )

    assert (
        registry.editor_lifecycle_state("wf-a")
        == WorkflowSurfaceLifecycleState.MATERIALIZED_UNPROJECTED
    )

    clean_registry = WorkflowSurfaceRegistry(
        editor_panels={"wf-a": _ProjectionAwareEditorPanel(clean=True)},
        cube_stacks={"wf-a": object()},
        override_managers={"wf-a": object()},
        workflows={"wf-a": workflow},
    )

    assert (
        clean_registry.editor_lifecycle_state("wf-a")
        == WorkflowSurfaceLifecycleState.CLEAN
    )


def test_registry_reports_dirty_editor_from_invalidation_state() -> None:
    """Dirty invalidation should take precedence over cached projection proof."""

    invalidation = WorkflowSurfaceInvalidationService()
    invalidation.mark_dirty(
        "wf-a",
        {WorkflowSurface.EDITOR},
        WorkflowInvalidationReason.CUBE_ADDED,
    )
    workflow = SimpleNamespace(cubes={}, stack_order=[])
    registry = WorkflowSurfaceRegistry(
        editor_panels={"wf-a": _ProjectionAwareEditorPanel(clean=True)},
        cube_stacks={"wf-a": object()},
        override_managers={"wf-a": object()},
        workflows={"wf-a": workflow},
        surface_invalidation_service=invalidation,
    )

    assert (
        registry.editor_lifecycle_state("wf-a") == WorkflowSurfaceLifecycleState.DIRTY
    )


def test_registry_reports_unmaterialized_editor_without_creating_widgets() -> None:
    """Missing workflow UI should be observable without side effects."""

    registry = WorkflowSurfaceRegistry(
        editor_panels={},
        cube_stacks={},
        override_managers={},
        workflows={"wf-a": object()},
    )

    assert (
        registry.editor_lifecycle_state("wf-a")
        == WorkflowSurfaceLifecycleState.UNMATERIALIZED
    )
    assert registry.editor_panel("wf-a") is None
