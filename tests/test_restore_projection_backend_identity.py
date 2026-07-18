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

"""Tests for live restore projection backend identity collection."""

from __future__ import annotations

from dataclasses import dataclass, field

from substitute.application.cubes import LoadedCubeDefinition
from substitute.application.workspace_state.restore_projection_backend_identity import (
    RestoreProjectionBackendIdentityService,
)
from substitute.application.workspace_state.restore_projection_identity import (
    cube_definition_fingerprint,
    node_definition_fingerprint,
)
from substitute.application.workspace_state.restore_projection_models import (
    APP_PROJECTION_VERSION,
    RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
    CachedCubeProjection,
    CachedCubeStackProjection,
    CachedEditorSectionProjection,
    CachedWorkflowProjection,
    RestoreProjectionArtifact,
)
from substitute.domain.workflow import WorkflowDocumentKind


@dataclass
class _CubeLoader:
    """Return one configured live definition and record its identity request."""

    definition: LoadedCubeDefinition
    calls: list[tuple[str, str]] = field(default_factory=list)

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return the configured versioned definition."""

        _ = cube_load_trace_id
        self.calls.append((cube_id, version))
        return self.definition


class _NodeGateway:
    """Return one configured live node definition."""

    def __init__(self, definition: dict[str, object]) -> None:
        """Store the live definition."""

        self.definition = definition

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the configured definition for the requested class."""

        assert node_class == "KSampler"
        return self.definition


def test_backend_identity_collects_collision_free_cube_and_node_fingerprints() -> None:
    """Live validation identity should match capture identity for cubes and nodes."""

    definition = LoadedCubeDefinition(
        cube_id="cube.scene",
        version="1.0.0",
        display_name="Scene",
        graph={"nodes": {"1": {"class_type": "KSampler"}}},
        ui_payload={
            "canonical_cube": {"cube_id": "cube.scene"},
            "content_hash": "hash",
            "catalog_revision": "revision",
        },
    )
    node_definition: dict[str, object] = {"input": {"required": {"seed": ["INT", {}]}}}
    loader = _CubeLoader(definition)

    identity = RestoreProjectionBackendIdentityService().collect(
        _artifact(definition, node_definition),
        cube_loader=loader,
        node_definition_gateway=_NodeGateway(node_definition),
    )

    assert loader.calls == [("cube.scene", "1.0.0")]
    assert identity.cube_fingerprints == {
        "workflow-a:Scene": cube_definition_fingerprint(definition)
    }
    assert identity.node_fingerprints == {
        "KSampler": node_definition_fingerprint(node_definition)
    }


def _artifact(
    definition: LoadedCubeDefinition,
    node_definition: dict[str, object],
) -> RestoreProjectionArtifact:
    """Build a cache artifact containing one cube and live node class."""

    section = CachedEditorSectionProjection(
        section_key="Scene",
        buffer_fingerprint="buffer",
        node_classes=("KSampler",),
        node_definition_fingerprint_by_class={
            "KSampler": node_definition_fingerprint(node_definition)
        },
        projected_node_order=("1",),
    )
    workflow = CachedWorkflowProjection(
        workflow_id="workflow-a",
        tab_label="Workflow A",
        document_kind=WorkflowDocumentKind.CUBE_STACK,
        workflow_fingerprint="workflow",
        cube_stack=CachedCubeStackProjection(
            stack_order=("Scene",),
            active_cube_alias="Scene",
            cubes=(
                CachedCubeProjection(
                    requested_cube_id=definition.cube_id,
                    canonical_cube_id=definition.cube_id,
                    cube_version=definition.version,
                    content_hash="hash",
                    catalog_revision="revision",
                    section=section,
                ),
            ),
        ),
    )
    return RestoreProjectionArtifact(
        schema_version=RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
        created_at="2026-07-16T00:00:00Z",
        app_projection_version=APP_PROJECTION_VERSION,
        target_key="target",
        workspace_fingerprint="workspace",
        active_route="workflow-a",
        active_workflow_id="workflow-a",
        workflows=(workflow,),
        prompt_editor_feature_profile_fingerprint="prompt",
        node_definition_fingerprints={
            "KSampler": node_definition_fingerprint(node_definition)
        },
        cube_definition_fingerprints={
            "workflow-a:Scene": cube_definition_fingerprint(definition)
        },
    )
