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

"""Hydrate restored workspace snapshots through canonical cube runtime loading."""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace

from substitute.application.cubes import LoadedCubeDefinition
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_warning,
)
from substitute.shared.startup_trace import trace_mark, trace_span

from .cube_runtime_hydrator import (
    CubeRuntimeHydrator,
    CubeRuntimeLoadServiceProtocol,
    NodeBehaviorRuntimeServiceProtocol,
    restore_cube_buffer_patch,
)
from .native_graph_restore_service import (
    CubeWorkflowAnalyzerProtocol,
    NativeGraphRestoreService,
)

_LOGGER = get_logger("application.workspace_state.workspace_runtime_hydration_service")


@dataclass(frozen=True, slots=True)
class WorkspaceRuntimeHydrationResult:
    """Describe a workspace snapshot after canonical runtime hydration."""

    snapshot: WorkspaceSnapshot
    warnings: tuple[str, ...]


class WorkspaceRuntimeHydrationService:
    """Build live restored workflow state with the normal cube runtime builder."""

    def __init__(
        self,
        *,
        cube_load_service: CubeRuntimeLoadServiceProtocol,
        node_behavior_service: NodeBehaviorRuntimeServiceProtocol,
        cube_workflow_analyzer: CubeWorkflowAnalyzerProtocol | None = None,
        preserve_cube_keys: frozenset[tuple[str, str]] = frozenset(),
    ) -> None:
        """Store services used to canonicalize restored cube runtime state."""

        self._cube_runtime_hydrator = CubeRuntimeHydrator(
            cube_load_service=cube_load_service,
            node_behavior_service=node_behavior_service,
        )
        self._native_graph_restore = (
            NativeGraphRestoreService(cube_workflow_analyzer)
            if cube_workflow_analyzer is not None
            else None
        )
        self._preserve_cube_keys = preserve_cube_keys

    def hydrate(self, snapshot: WorkspaceSnapshot) -> WorkspaceRuntimeHydrationResult:
        """Return a snapshot whose workflows contain canonical live cube state."""

        warnings: list[str] = []
        loaded_definitions: dict[tuple[str, str], LoadedCubeDefinition] = {}
        workflows_by_id = {
            workflow.workflow_id: workflow for workflow in snapshot.workflows
        }
        active_workflow_id = _active_workflow_id(snapshot)
        hydration_order = _workflow_hydration_order(snapshot, active_workflow_id)
        hydrated_by_id: dict[str, WorkflowSnapshot] = {}
        trace_mark(
            "workspace_runtime_hydration.start",
            active_workflow_id=active_workflow_id,
            workflow_count=len(snapshot.workflows),
            hydration_order=hydration_order,
        )
        log_debug(
            _LOGGER,
            "workspace runtime hydration started",
            active_workflow_id=active_workflow_id,
            workflow_count=len(snapshot.workflows),
            tab_order=snapshot.tab_order,
        )
        for workflow_id in hydration_order:
            workflow = workflows_by_id.get(workflow_id)
            if workflow is None:
                continue
            with trace_span(
                "workspace_runtime_hydration.workflow",
                workflow_id=workflow.workflow_id,
                cube_count=len(workflow.workflow.cubes),
                stack_order_length=len(workflow.workflow.stack_order),
            ):
                hydrated_by_id[workflow_id] = self._hydrate_workflow(
                    workflow,
                    loaded_definitions=loaded_definitions,
                    warnings=warnings,
                )
        hydrated_workflows = tuple(
            hydrated_by_id.get(workflow.workflow_id, workflow)
            for workflow in snapshot.workflows
        )
        log_info(
            _LOGGER,
            "workspace runtime hydration completed",
            workflow_count=len(hydrated_workflows),
            warning_count=len(warnings),
            cached_definition_count=len(loaded_definitions),
        )
        trace_mark(
            "workspace_runtime_hydration.end",
            workflow_count=len(hydrated_workflows),
            warning_count=len(warnings),
            cached_definition_count=len(loaded_definitions),
        )
        return WorkspaceRuntimeHydrationResult(
            snapshot=replace(snapshot, workflows=hydrated_workflows),
            warnings=tuple(warnings),
        )

    def _hydrate_workflow(
        self,
        snapshot: WorkflowSnapshot,
        *,
        loaded_definitions: dict[tuple[str, str], LoadedCubeDefinition],
        warnings: list[str],
    ) -> WorkflowSnapshot:
        """Return one workflow snapshot with hydrated cube runtime state."""

        workflow = snapshot.workflow
        if workflow.direct_workflow is not None:
            if self._native_graph_restore is None:
                return replace(snapshot, active_cube_alias=None)
            result = self._native_graph_restore.restore(snapshot)
            if result.warning is not None:
                warnings.append(result.warning)
                return result.snapshot
            return self._hydrate_graph_workflow(
                result.snapshot,
                loaded_definitions=loaded_definitions,
                warnings=warnings,
            )
        hydrated_cubes: dict[str, CubeState] = {}
        hydrated_stack_order: list[str] = []
        for alias in workflow.stack_order:
            cube_state = workflow.cubes.get(alias)
            if cube_state is None:
                warning = (
                    f"Skipped restored cube alias {alias} in workflow "
                    f"{snapshot.workflow_id} because no cube state was present."
                )
                warnings.append(warning)
                log_warning(
                    _LOGGER,
                    "restore runtime hydration skipped missing cube state",
                    workflow_id=snapshot.workflow_id,
                    cube_alias=alias,
                )
                continue
            if (snapshot.workflow_id, alias) in self._preserve_cube_keys:
                hydrated_cubes[alias] = copy.deepcopy(cube_state)
                hydrated_stack_order.append(alias)
                log_debug(
                    _LOGGER,
                    "restore runtime hydration preserved stale cube state",
                    workflow_id=snapshot.workflow_id,
                    cube_alias=alias,
                    cube_id=cube_state.cube_id,
                    cube_version=cube_state.version,
                )
                continue
            hydrated_cube = self._cube_runtime_hydrator.hydrate(
                workflow_id=snapshot.workflow_id,
                cube_state=cube_state,
                loaded_definitions=loaded_definitions,
                warnings=warnings,
            )
            if hydrated_cube is None:
                continue
            hydrated_cubes[alias] = hydrated_cube
            hydrated_stack_order.append(alias)
        active_cube_alias = (
            snapshot.active_cube_alias
            if snapshot.active_cube_alias in hydrated_cubes
            else (hydrated_stack_order[0] if hydrated_stack_order else None)
        )
        hydrated_snapshot = replace(
            snapshot,
            workflow=_replace_cube_runtime(
                workflow,
                cubes=hydrated_cubes,
                stack_order=hydrated_stack_order,
            ),
            active_cube_alias=active_cube_alias,
            editor_viewport=_repair_editor_viewport_anchor(
                snapshot.editor_viewport,
                hydrated_aliases=set(hydrated_cubes),
                active_cube_alias=active_cube_alias,
            ),
        )
        if self._native_graph_restore is None:
            return hydrated_snapshot
        migration = self._native_graph_restore.migrate_legacy(hydrated_snapshot)
        if migration.warning is not None:
            warnings.append(migration.warning)
        return migration.snapshot

    def _hydrate_graph_workflow(
        self,
        snapshot: WorkflowSnapshot,
        *,
        loaded_definitions: dict[tuple[str, str], LoadedCubeDefinition],
        warnings: list[str],
    ) -> WorkflowSnapshot:
        """Hydrate graph projections while the canonical graph remains authoritative."""

        workflow = snapshot.workflow
        direct = workflow.direct_workflow
        if direct is None:
            raise ValueError("Graph Cube hydration requires a canonical workflow.")
        hydrated_cubes: dict[str, CubeState] = {}
        for alias in workflow.stack_order:
            cube = workflow.cubes[alias]
            if (snapshot.workflow_id, alias) in self._preserve_cube_keys:
                hydrated_cubes[alias] = copy.deepcopy(cube)
                continue
            hydrated = self._cube_runtime_hydrator.hydrate(
                workflow_id=snapshot.workflow_id,
                cube_state=cube,
                loaded_definitions=loaded_definitions,
                warnings=warnings,
            )
            if hydrated is not None:
                hydrated_cubes[alias] = hydrated
        workflow.install_canonical_graph(
            direct,
            projection_sources=hydrated_cubes,
        )
        active_cube_alias = (
            snapshot.active_cube_alias
            if snapshot.active_cube_alias in workflow.cubes
            else (workflow.stack_order[0] if workflow.stack_order else None)
        )
        return replace(
            snapshot,
            workflow=workflow,
            active_cube_alias=active_cube_alias,
            editor_viewport=_repair_editor_viewport_anchor(
                snapshot.editor_viewport,
                hydrated_aliases=set(workflow.cubes),
                active_cube_alias=active_cube_alias,
            ),
        )


def _repair_editor_viewport_anchor(
    viewport: EditorViewportSnapshot | None,
    *,
    hydrated_aliases: set[str],
    active_cube_alias: str | None,
) -> EditorViewportSnapshot | None:
    """Return viewport state whose anchor still references a hydrated cube."""

    if viewport is None:
        return None
    if viewport.anchor_cube_alias in hydrated_aliases:
        return viewport
    return replace(viewport, anchor_cube_alias=active_cube_alias)


def _replace_cube_runtime(
    workflow: WorkflowState,
    *,
    cubes: dict[str, CubeState],
    stack_order: list[str],
) -> WorkflowState:
    """Return an isolated workflow copy with hydrated cube-owned state."""

    return replace(
        copy.deepcopy(workflow),
        cubes=cubes,
        stack_order=stack_order,
    )


def _active_workflow_id(snapshot: WorkspaceSnapshot) -> str:
    """Return normalized active workflow id for hydration prioritization."""

    if snapshot.active_workflow_id in snapshot.tab_order:
        return snapshot.active_workflow_id
    if snapshot.active_route in snapshot.tab_order:
        return snapshot.active_route
    return ""


def _workflow_hydration_order(
    snapshot: WorkspaceSnapshot,
    active_workflow_id: str,
) -> tuple[str, ...]:
    """Return active-first workflow hydration order without changing tab order."""

    ordered = list(snapshot.tab_order)
    if active_workflow_id in ordered:
        ordered.remove(active_workflow_id)
        ordered.insert(0, active_workflow_id)
    return tuple(ordered)


__all__ = [
    "CubeWorkflowAnalyzerProtocol",
    "CubeRuntimeLoadServiceProtocol",
    "NodeBehaviorRuntimeServiceProtocol",
    "WorkspaceRuntimeHydrationResult",
    "WorkspaceRuntimeHydrationService",
    "restore_cube_buffer_patch",
]
