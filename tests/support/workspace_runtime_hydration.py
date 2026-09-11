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

"""Provide reusable deterministic workspace-hydration test collaborators."""

from __future__ import annotations

from dataclasses import dataclass, field

from substitute.application.cubes import LoadedCubeDefinition, LoadedCubeRuntime
from substitute.application.node_behavior import NodeBehaviorRuntimeState
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)


@dataclass
class CubeLoaderStub:
    """Record versioned load calls and build deterministic runtimes."""

    load_calls: list[tuple[str, str]] = field(default_factory=list)

    def load_cube_definition(
        self,
        cube_id: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return a latest cube definition for protocol completeness."""

        return self.load_cube_definition_version(
            cube_id,
            "latest",
            cube_load_trace_id=cube_load_trace_id,
        )

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return one loaded cube definition by version."""

        _ = cube_load_trace_id
        self.load_calls.append((cube_id, version))
        return LoadedCubeDefinition(
            cube_id=cube_id,
            version=version,
            display_name=cube_id,
            graph={"nodes": {}, "version": version},
            ui_payload={
                "catalog_revision": "rev",
                "canonical_cube": {
                    "cube_id": cube_id,
                    "version": version,
                    "description": "Canonical description",
                    "metadata": {
                        "default_alias": "Anima/Prompt by Region",
                        "target_model": "Anima",
                    },
                    "surface": {"default_flavor_id": "default", "controls": []},
                    "flavors": {
                        "authored": [{"id": "default", "name": "Default", "values": {}}]
                    },
                },
            },
        )

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
        """Build a runtime from the preloaded definition."""

        _ = buffer_patch, runtime_state, cube_load_trace_id
        if loaded_cube_definition is None:
            raise RuntimeError("expected loaded cube definition")
        cube_state = CubeState(
            cube_id=cube_id,
            version=loaded_cube_definition.version,
            alias=alias_name,
            original_cube=loaded_cube_definition.graph,
            buffer=loaded_cube_definition.graph,
            ui=loaded_cube_definition.ui_payload,
        )
        return LoadedCubeRuntime(
            cube_id=cube_id,
            version=loaded_cube_definition.version,
            display_name=loaded_cube_definition.display_name,
            cube_definition=loaded_cube_definition.graph,
            cube_buffer=loaded_cube_definition.graph,
            cube_state=cube_state,
            ui_payload=loaded_cube_definition.ui_payload,
        )


class NodeBehaviorStub:
    """Return no-op node behavior state."""

    def prepare_runtime_state(
        self,
        loaded_cube: LoadedCubeDefinition,
        alias_name: str,
    ) -> NodeBehaviorRuntimeState:
        """Return deterministic runtime state."""

        _ = loaded_cube, alias_name
        return NodeBehaviorRuntimeState()


def workspace_snapshot(cubes: list[CubeState]) -> WorkspaceSnapshot:
    """Build a one-workflow snapshot."""

    workflow = WorkflowState(
        cubes={cube.alias: cube for cube in cubes},
        stack_order=[cube.alias for cube in cubes],
    )
    return WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="workflow-1",
                tab_label="Workflow",
                workflow=workflow,
            ),
        ),
        tab_order=("workflow-1",),
        active_route="workflow-1",
        active_workflow_id="workflow-1",
    )


def cube_state(*, alias: str, version: str, bypassed: bool = False) -> CubeState:
    """Build a restored cube state."""

    return CubeState(
        cube_id="owner/repo/demo.cube",
        version=version,
        alias=alias,
        original_cube={"nodes": {}},
        buffer={"nodes": {}},
        bypassed=bypassed,
    )


__all__ = ["CubeLoaderStub", "NodeBehaviorStub", "cube_state", "workspace_snapshot"]
