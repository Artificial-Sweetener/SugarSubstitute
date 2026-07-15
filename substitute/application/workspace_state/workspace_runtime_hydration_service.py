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
from typing import Protocol

from substitute.application.cubes import LoadedCubeDefinition, LoadedCubeRuntime
from substitute.application.cubes.cube_instance_state_transfer import (
    structural_patch_keys,
)
from substitute.application.node_behavior import NodeBehaviorRuntimeState
from substitute.domain.common import JsonObject
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

_LOGGER = get_logger("application.workspace_state.workspace_runtime_hydration_service")
_RUNTIME_OWNED_CUBE_UI_KEYS = frozenset(
    {
        "artifact_label",
        "canonical_cube",
        "catalog_revision",
        "content_hash",
        "cube_icon",
        "node_behavior_runtime",
        "path",
        "schema_version",
        "source",
    }
)


class CubeRuntimeLoadServiceProtocol(Protocol):
    """Describe cube runtime loading operations required by restore hydration."""

    def load_cube_definition(
        self,
        cube_id: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return one loaded cube definition for runtime hydration."""

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return one versioned loaded cube definition for runtime hydration."""

    def build_loaded_cube_runtime(
        self,
        cube_id: str,
        alias_name: str,
        *,
        buffer_patch: object | None,
        runtime_state: object | None,
        loaded_cube_definition: LoadedCubeDefinition | None = None,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeRuntime:
        """Return a canonical live cube runtime state."""


class NodeBehaviorRuntimeServiceProtocol(Protocol):
    """Describe node behavior runtime preparation required by restore hydration."""

    def prepare_runtime_state(
        self,
        loaded_cube: LoadedCubeDefinition,
        alias_name: str,
    ) -> NodeBehaviorRuntimeState:
        """Return one node behavior runtime state for a loaded cube."""


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
        preserve_cube_keys: frozenset[tuple[str, str]] = frozenset(),
    ) -> None:
        """Store services used to canonicalize restored cube runtime state."""

        self._cube_load_service = cube_load_service
        self._node_behavior_service = node_behavior_service
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
            hydrated_cube = self._hydrate_cube(
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
        return replace(
            snapshot,
            workflow=_copy_workflow_with_cubes(
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

    def _hydrate_cube(
        self,
        *,
        workflow_id: str,
        cube_state: CubeState,
        loaded_definitions: dict[tuple[str, str], LoadedCubeDefinition],
        warnings: list[str],
    ) -> CubeState | None:
        """Return one restored cube rebuilt through the canonical runtime path."""

        cube_id = cube_state.cube_id.strip()
        alias = cube_state.alias.strip() or cube_state.alias
        version = cube_state.version.strip()
        trace_mark(
            "workspace_runtime_hydration.cube.start",
            workflow_id=workflow_id,
            cube_alias=alias,
            cube_id=cube_id,
        )
        if not cube_id:
            warning = (
                f"Skipped restored cube alias {cube_state.alias} in workflow "
                f"{workflow_id} because its cube id is empty."
            )
            warnings.append(warning)
            log_warning(
                _LOGGER,
                "restore runtime hydration skipped empty cube id",
                workflow_id=workflow_id,
                cube_alias=cube_state.alias,
            )
            return None
        if not version:
            warning = (
                f"Skipped restored cube {alias} in workflow {workflow_id} because "
                f"cube {cube_id} has no persisted cube version."
            )
            warnings.append(warning)
            log_warning(
                _LOGGER,
                "restore runtime hydration skipped cube without version",
                workflow_id=workflow_id,
                cube_alias=alias,
                cube_id=cube_id,
            )
            return None
        try:
            definition_key = (cube_id, version)
            loaded_cube = loaded_definitions.get(definition_key)
            if loaded_cube is None:
                with trace_span(
                    "workspace_runtime_hydration.cube.load_definition",
                    workflow_id=workflow_id,
                    cube_alias=alias,
                    cube_id=cube_id,
                    cube_version=version,
                ):
                    loaded_cube = self._cube_load_service.load_cube_definition_version(
                        cube_id,
                        version,
                        cube_load_trace_id=f"restore:{workflow_id}:{alias}",
                    )
                loaded_definitions[definition_key] = loaded_cube
            else:
                trace_mark(
                    "workspace_runtime_hydration.cube.definition_cache_hit",
                    workflow_id=workflow_id,
                    cube_alias=alias,
                    cube_id=cube_id,
                    cube_version=version,
                )
            with trace_span(
                "workspace_runtime_hydration.cube.prepare_node_behavior",
                workflow_id=workflow_id,
                cube_alias=alias,
                cube_id=cube_id,
            ):
                runtime_state = self._node_behavior_service.prepare_runtime_state(
                    loaded_cube,
                    alias,
                )
            with trace_span(
                "workspace_runtime_hydration.cube.build_runtime",
                workflow_id=workflow_id,
                cube_alias=alias,
                cube_id=cube_id,
            ):
                loaded_runtime = self._cube_load_service.build_loaded_cube_runtime(
                    cube_id,
                    alias,
                    buffer_patch=restore_cube_buffer_patch(cube_state),
                    runtime_state=runtime_state,
                    loaded_cube_definition=loaded_cube,
                    cube_load_trace_id=f"restore:{workflow_id}:{alias}",
                )
        except (LookupError, OSError, RuntimeError, TypeError, ValueError) as error:
            trace_mark(
                "workspace_runtime_hydration.cube.preserve_restored_state",
                workflow_id=workflow_id,
                cube_alias=alias,
                cube_id=cube_id,
                error=repr(error),
            )
            warning = (
                f"Preserved restored cube {alias} in workflow {workflow_id} because "
                f"runtime hydration failed for cube {cube_id}."
            )
            warnings.append(warning)
            log_warning(
                _LOGGER,
                "restore runtime hydration preserved restored cube state",
                workflow_id=workflow_id,
                cube_alias=alias,
                cube_id=cube_id,
                error=error,
            )
            return copy.deepcopy(cube_state)
        trace_mark(
            "workspace_runtime_hydration.cube.end",
            workflow_id=workflow_id,
            cube_alias=alias,
            cube_id=cube_id,
        )
        return _merge_persistent_cube_state(
            hydrated_cube=loaded_runtime.cube_state,
            restored_cube=cube_state,
        )


def restore_cube_buffer_patch(cube_state: CubeState) -> JsonObject:
    """Return loader patch data from a persisted restored cube state."""

    patch: JsonObject = {
        "cube_id": cube_state.cube_id,
        "version": cube_state.version,
    }
    buffer = cube_state.buffer
    for key, value in buffer.items():
        if key in {
            "cube_id",
            "version",
            *structural_patch_keys(),
        }:
            continue
        if isinstance(key, str):
            patch[key] = copy.deepcopy(value)
    return patch


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


def _merge_persistent_cube_state(
    *,
    hydrated_cube: CubeState,
    restored_cube: CubeState,
) -> CubeState:
    """Preserve restored workflow-owned cube state after runtime hydration."""

    hydrated_cube.update_policy = restored_cube.update_policy
    hydrated_cube.bypassed = restored_cube.bypassed
    restored_ui = restored_cube.ui
    if not isinstance(restored_ui, dict):
        return hydrated_cube
    durable_ui = {
        key: copy.deepcopy(value)
        for key, value in restored_ui.items()
        if key not in _RUNTIME_OWNED_CUBE_UI_KEYS
    }
    if not durable_ui:
        return hydrated_cube
    hydrated_ui = (
        copy.deepcopy(hydrated_cube.ui) if isinstance(hydrated_cube.ui, dict) else {}
    )
    hydrated_ui.update(durable_ui)
    hydrated_cube.ui = hydrated_ui
    return hydrated_cube


def _copy_workflow_with_cubes(
    workflow: WorkflowState,
    *,
    cubes: dict[str, CubeState],
    stack_order: list[str],
) -> WorkflowState:
    """Return a workflow copy preserving non-cube restored workflow state."""

    return WorkflowState(
        cubes=cubes,
        stack_order=stack_order,
        metadata=copy.deepcopy(workflow.metadata),
        global_overrides=copy.deepcopy(workflow.global_overrides),
        override_control_states=copy.deepcopy(workflow.override_control_states),
        global_override_selections=copy.deepcopy(workflow.global_override_selections),
        canvas=copy.deepcopy(workflow.canvas),
        output_image_uuids=list(workflow.output_image_uuids),
        output_focus_mode=workflow.output_focus_mode,
        active_output_uuid=workflow.active_output_uuid,
        active_output_set_index=workflow.active_output_set_index,
        active_output_source_key=workflow.active_output_source_key,
        active_output_scene_key=workflow.active_output_scene_key,
        active_output_scene_overview=workflow.active_output_scene_overview,
        output_compare_state=workflow.output_compare_state,
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
    "CubeRuntimeLoadServiceProtocol",
    "NodeBehaviorRuntimeServiceProtocol",
    "WorkspaceRuntimeHydrationResult",
    "WorkspaceRuntimeHydrationService",
    "restore_cube_buffer_patch",
]
