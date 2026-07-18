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

"""Resolve live backend identities required for projection cache validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.application.cubes import LoadedCubeDefinition
from substitute.application.workspace_state.restore_projection_identity import (
    cube_definition_fingerprint,
    cube_projection_cache_key,
    node_definition_fingerprint,
)
from substitute.application.workspace_state.restore_projection_models import (
    RestoreProjectionArtifact,
)


class RestoreProjectionCubeLoader(Protocol):
    """Load the exact cube definition referenced by a cache artifact."""

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return one versioned cube definition."""


class RestoreProjectionNodeDefinitionGateway(Protocol):
    """Return live Comfy node definitions by class."""

    def get_node_definition(self, node_class: str) -> Mapping[str, object]:
        """Return one live node definition payload."""


@dataclass(frozen=True, slots=True)
class RestoreProjectionBackendIdentity:
    """Store live identities comparable with one cached artifact."""

    cube_fingerprints: Mapping[str, str]
    node_fingerprints: Mapping[str, str]


class RestoreProjectionBackendIdentityService:
    """Collect exact live identities for post-backend cache validation."""

    def collect(
        self,
        artifact: RestoreProjectionArtifact,
        *,
        cube_loader: RestoreProjectionCubeLoader,
        node_definition_gateway: RestoreProjectionNodeDefinitionGateway,
    ) -> RestoreProjectionBackendIdentity:
        """Return live cube and node fingerprints requested by the artifact."""

        cube_fingerprints: dict[str, str] = {}
        for workflow in artifact.workflows:
            cube_stack = workflow.cube_stack
            for cube in cube_stack.cubes if cube_stack is not None else ():
                definition = cube_loader.load_cube_definition_version(
                    cube.requested_cube_id,
                    cube.cube_version,
                    cube_load_trace_id=(
                        f"restore_projection_validation:{workflow.workflow_id}:{cube.alias}"
                    ),
                )
                cube_fingerprints[
                    cube_projection_cache_key(workflow.workflow_id, cube.alias)
                ] = cube_definition_fingerprint(definition)
        node_fingerprints = {
            node_class: node_definition_fingerprint(
                node_definition_gateway.get_node_definition(node_class)
            )
            for node_class in artifact.node_definition_fingerprints
        }
        return RestoreProjectionBackendIdentity(
            cube_fingerprints=cube_fingerprints,
            node_fingerprints=node_fingerprints,
        )


__all__ = [
    "RestoreProjectionBackendIdentity",
    "RestoreProjectionBackendIdentityService",
    "RestoreProjectionCubeLoader",
    "RestoreProjectionNodeDefinitionGateway",
]
