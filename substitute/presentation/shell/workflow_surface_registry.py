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

"""Describe workflow presentation surface ownership and lifecycle state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, cast

from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurface,
    WorkflowSurfaceDirtyState,
)


class WorkflowSurfaceOwnership(StrEnum):
    """Classify how a workflow surface is owned by the shell."""

    PER_WORKFLOW_CACHED = "per_workflow_cached"
    SHARED_ROUTE_PROJECTED = "shared_route_projected"
    DURABLE_SESSION = "durable_session"


class WorkflowSurfaceLifecycleState(StrEnum):
    """Describe the projection state of a workflow presentation surface."""

    UNMATERIALIZED = "unmaterialized"
    MATERIALIZED_UNPROJECTED = "materialized_unprojected"
    CLEAN = "clean"
    DIRTY = "dirty"
    RECONCILING = "reconciling"
    FAILED = "failed"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class WorkflowSurfaceDescriptor:
    """Describe one workflow surface family for routing and reconciliation."""

    surface: WorkflowSurface
    ownership: WorkflowSurfaceOwnership
    owner_name: str


class EditorProjectionProbe(Protocol):
    """Describe editor-panel projection-cleanliness probes."""

    def current_projection_signature(
        self,
        *,
        workflow_id: str,
        cube_entries: list[tuple[str, object]],
        cube_states: Mapping[str, object],
        stack_order: list[str],
    ) -> object | None:
        """Return the signature for the requested workflow projection."""

    def is_projection_clean(self, signature: object) -> bool:
        """Return whether the supplied signature is already rendered."""


class WorkflowSurfaceInvalidationStateProtocol(Protocol):
    """Describe dirty-state access needed for lifecycle classification."""

    def dirty_state(self, workflow_id: str) -> WorkflowSurfaceDirtyState:
        """Return current dirty state for one workflow."""


class WorkflowSurfaceRegistry:
    """Expose workflow surface topology without exposing the whole shell."""

    _DESCRIPTORS: Mapping[WorkflowSurface, WorkflowSurfaceDescriptor] = {
        WorkflowSurface.EDITOR: WorkflowSurfaceDescriptor(
            surface=WorkflowSurface.EDITOR,
            ownership=WorkflowSurfaceOwnership.PER_WORKFLOW_CACHED,
            owner_name="EditorPanel",
        ),
        WorkflowSurface.CANVAS: WorkflowSurfaceDescriptor(
            surface=WorkflowSurface.CANVAS,
            ownership=WorkflowSurfaceOwnership.SHARED_ROUTE_PROJECTED,
            owner_name="WorkflowCanvasProjectionCoordinator",
        ),
        WorkflowSurface.OVERRIDES: WorkflowSurfaceDescriptor(
            surface=WorkflowSurface.OVERRIDES,
            ownership=WorkflowSurfaceOwnership.PER_WORKFLOW_CACHED,
            owner_name="GlobalOverridesManager",
        ),
        WorkflowSurface.GENERATION_AVAILABILITY: WorkflowSurfaceDescriptor(
            surface=WorkflowSurface.GENERATION_AVAILABILITY,
            ownership=WorkflowSurfaceOwnership.SHARED_ROUTE_PROJECTED,
            owner_name="ShellGenerationActions",
        ),
    }

    def __init__(
        self,
        *,
        editor_panels: Mapping[str, object],
        cube_stacks: Mapping[str, object],
        override_managers: Mapping[str, object | None],
        workflows: Mapping[str, object],
        surface_invalidation_service: (
            WorkflowSurfaceInvalidationStateProtocol | None
        ) = None,
    ) -> None:
        """Store narrow surface maps for topology and lifecycle queries."""

        self._editor_panels = editor_panels
        self._cube_stacks = cube_stacks
        self._override_managers = override_managers
        self._workflows = workflows
        self._surface_invalidation_service = surface_invalidation_service

    def descriptor(self, surface: WorkflowSurface) -> WorkflowSurfaceDescriptor:
        """Return the ownership descriptor for one surface family."""

        return self._DESCRIPTORS[surface]

    def editor_panel(self, workflow_id: str) -> object | None:
        """Return the existing editor panel without materializing one."""

        return self._editor_panels.get(workflow_id)

    def cube_stack(self, workflow_id: str) -> object | None:
        """Return the existing cube stack without materializing one."""

        return self._cube_stacks.get(workflow_id)

    def override_manager(self, workflow_id: str) -> object | None:
        """Return the existing override manager without materializing one."""

        return self._override_managers.get(workflow_id)

    def workflow_ui_materialized(self, workflow_id: str) -> bool:
        """Return whether cached editor and cube-stack widgets already exist."""

        return workflow_id in self._editor_panels and workflow_id in self._cube_stacks

    def editor_lifecycle_state(
        self,
        workflow_id: str,
    ) -> WorkflowSurfaceLifecycleState:
        """Return the editor surface lifecycle state for one workflow."""

        if self._editor_is_dirty(workflow_id):
            return WorkflowSurfaceLifecycleState.DIRTY
        editor_panel = self._editor_panels.get(workflow_id)
        workflow = self._workflows.get(workflow_id)
        if editor_panel is None or workflow is None:
            return WorkflowSurfaceLifecycleState.UNMATERIALIZED
        current_projection_signature = getattr(
            editor_panel,
            "current_projection_signature",
            None,
        )
        is_projection_clean = getattr(editor_panel, "is_projection_clean", None)
        if not callable(current_projection_signature) or not callable(
            is_projection_clean
        ):
            return WorkflowSurfaceLifecycleState.CLEAN
        cube_states_object = getattr(workflow, "cubes", {})
        if not isinstance(cube_states_object, Mapping):
            return WorkflowSurfaceLifecycleState.MATERIALIZED_UNPROJECTED
        cube_states = cast(Mapping[str, object], cube_states_object)
        stack_order_object = getattr(workflow, "stack_order", ())
        if not isinstance(stack_order_object, (list, tuple)):
            return WorkflowSurfaceLifecycleState.MATERIALIZED_UNPROJECTED
        stack_order = [str(alias) for alias in stack_order_object]
        try:
            cube_entries = [(alias, cube_states[alias]) for alias in stack_order]
            probe = cast(EditorProjectionProbe, editor_panel)
            projection_signature = probe.current_projection_signature(
                workflow_id=workflow_id,
                cube_entries=cube_entries,
                cube_states=cube_states,
                stack_order=stack_order,
            )
        except (KeyError, TypeError, ValueError):
            return WorkflowSurfaceLifecycleState.MATERIALIZED_UNPROJECTED
        if projection_signature is None:
            return WorkflowSurfaceLifecycleState.MATERIALIZED_UNPROJECTED
        if probe.is_projection_clean(projection_signature):
            return WorkflowSurfaceLifecycleState.CLEAN
        return WorkflowSurfaceLifecycleState.MATERIALIZED_UNPROJECTED

    def _editor_is_dirty(self, workflow_id: str) -> bool:
        """Return whether the invalidation state currently requires editor work."""

        if self._surface_invalidation_service is None:
            return False
        return (
            WorkflowSurface.EDITOR
            in self._surface_invalidation_service.dirty_state(
                workflow_id
            ).dirty_surfaces
        )


__all__ = [
    "EditorProjectionProbe",
    "WorkflowSurfaceDescriptor",
    "WorkflowSurfaceInvalidationStateProtocol",
    "WorkflowSurfaceLifecycleState",
    "WorkflowSurfaceOwnership",
    "WorkflowSurfaceRegistry",
]
