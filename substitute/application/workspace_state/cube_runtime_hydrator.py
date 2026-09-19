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

"""Hydrate one restored Cube through the canonical runtime-loading boundary."""

from __future__ import annotations

import copy
from typing import Protocol

from substitute.application.cubes import LoadedCubeDefinition, LoadedCubeRuntime
from substitute.application.cubes.cube_instance_state_transfer import (
    structural_patch_keys,
)
from substitute.application.node_behavior import NodeBehaviorRuntimeState
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState
from substitute.shared.logging.logger import get_logger, log_warning
from substitute.shared.startup_trace import trace_mark, trace_span

_LOGGER = get_logger("application.workspace_state.cube_runtime_hydrator")
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
    """Describe Cube runtime loading required by restored-state hydration."""

    def load_cube_definition(
        self,
        cube_id: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return one loaded Cube definition."""

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return one exact versioned Cube definition."""

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
        """Return canonical live Cube runtime state."""


class NodeBehaviorRuntimeServiceProtocol(Protocol):
    """Prepare node behavior collaborators for one loaded Cube."""

    def prepare_runtime_state(
        self,
        loaded_cube: LoadedCubeDefinition,
        alias_name: str,
    ) -> NodeBehaviorRuntimeState:
        """Return node behavior state for one Cube instance."""


class CubeRuntimeHydrator:
    """Rebuild restored Cube state through exact definition loading."""

    def __init__(
        self,
        *,
        cube_load_service: CubeRuntimeLoadServiceProtocol,
        node_behavior_service: NodeBehaviorRuntimeServiceProtocol,
    ) -> None:
        """Bind definition and behavior owners used during hydration."""

        self._cube_load_service = cube_load_service
        self._node_behavior_service = node_behavior_service

    def hydrate(
        self,
        *,
        workflow_id: str,
        cube_state: CubeState,
        loaded_definitions: dict[tuple[str, str], LoadedCubeDefinition],
        warnings: list[str],
    ) -> CubeState | None:
        """Return exact-definition runtime state with durable instance state merged."""

        cube_id = cube_state.cube_id.strip()
        alias = cube_state.alias.strip() or cube_state.alias
        version = cube_state.version.strip()
        trace_mark(
            "workspace_runtime_hydration.cube.start",
            workflow_id=workflow_id,
            cube_alias=alias,
            cube_id=cube_id,
        )
        if not cube_id or not version:
            missing = "cube id" if not cube_id else "persisted cube version"
            warning = (
                f"Skipped restored cube {alias} in workflow {workflow_id} because "
                f"it has no {missing}."
            )
            warnings.append(warning)
            log_warning(
                _LOGGER,
                "restore runtime hydration skipped incomplete Cube identity",
                workflow_id=workflow_id,
                cube_alias=alias,
                cube_id=cube_id,
                cube_version=version,
            )
            return None
        try:
            loaded_cube = self._load_definition(
                workflow_id=workflow_id,
                alias=alias,
                cube_id=cube_id,
                version=version,
                loaded_definitions=loaded_definitions,
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
                runtime = self._cube_load_service.build_loaded_cube_runtime(
                    cube_id,
                    alias,
                    buffer_patch=restore_cube_buffer_patch(cube_state),
                    runtime_state=runtime_state,
                    loaded_cube_definition=loaded_cube,
                    cube_load_trace_id=f"restore:{workflow_id}:{alias}",
                )
        except (LookupError, OSError, RuntimeError, TypeError, ValueError) as error:
            warning = (
                f"Preserved restored cube {alias} in workflow {workflow_id} because "
                f"runtime hydration failed for cube {cube_id}."
            )
            warnings.append(warning)
            log_warning(
                _LOGGER,
                "restore runtime hydration preserved restored Cube state",
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
            hydrated_cube=runtime.cube_state,
            restored_cube=cube_state,
        )

    def _load_definition(
        self,
        *,
        workflow_id: str,
        alias: str,
        cube_id: str,
        version: str,
        loaded_definitions: dict[tuple[str, str], LoadedCubeDefinition],
    ) -> LoadedCubeDefinition:
        """Load one exact definition once per workspace hydration."""

        definition_key = (cube_id, version)
        loaded = loaded_definitions.get(definition_key)
        if loaded is not None:
            trace_mark(
                "workspace_runtime_hydration.cube.definition_cache_hit",
                workflow_id=workflow_id,
                cube_alias=alias,
                cube_id=cube_id,
                cube_version=version,
            )
            return loaded
        with trace_span(
            "workspace_runtime_hydration.cube.load_definition",
            workflow_id=workflow_id,
            cube_alias=alias,
            cube_id=cube_id,
            cube_version=version,
        ):
            loaded = self._cube_load_service.load_cube_definition_version(
                cube_id,
                version,
                cube_load_trace_id=f"restore:{workflow_id}:{alias}",
            )
        loaded_definitions[definition_key] = loaded
        return loaded


def restore_cube_buffer_patch(cube_state: CubeState) -> JsonObject:
    """Return only persisted values allowed to overlay an exact definition."""

    patch: JsonObject = {"cube_id": cube_state.cube_id, "version": cube_state.version}
    for key, value in cube_state.buffer.items():
        if key in {"cube_id", "version", *structural_patch_keys()}:
            continue
        if isinstance(key, str):
            patch[key] = copy.deepcopy(value)
    return patch


def _merge_persistent_cube_state(
    *,
    hydrated_cube: CubeState,
    restored_cube: CubeState,
) -> CubeState:
    """Preserve workflow-owned state while exact runtime metadata stays authoritative."""

    hydrated_cube.undo_stack = copy.deepcopy(restored_cube.undo_stack)
    hydrated_cube.redo_stack = copy.deepcopy(restored_cube.redo_stack)
    hydrated_cube.dirty = restored_cube.dirty
    hydrated_cube.field_control_states = copy.deepcopy(
        restored_cube.field_control_states
    )
    hydrated_cube.update_policy = restored_cube.update_policy
    hydrated_cube.bypassed = restored_cube.bypassed
    hydrated_cube.output_persistence_enabled = restored_cube.output_persistence_enabled
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


__all__ = [
    "CubeRuntimeHydrator",
    "CubeRuntimeLoadServiceProtocol",
    "NodeBehaviorRuntimeServiceProtocol",
    "restore_cube_buffer_patch",
]
