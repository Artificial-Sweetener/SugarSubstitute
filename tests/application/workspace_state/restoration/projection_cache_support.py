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

"""Build restore-projection cache scenarios."""

from __future__ import annotations

from pathlib import Path


from substitute.application.workspace_state.restore_projection_identity import (
    fingerprint_json,
    workspace_projection_fingerprint,
)
from substitute.application.workspace_state.restore_projection_models import (
    RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
    CachedCubeProjection,
    CachedCubeStackProjection,
    CachedEditorSectionProjection,
    CachedNodeProjection,
    CachedWorkflowProjection,
    RestoreProjectionArtifact,
)
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot


def _artifact(
    workspace: WorkspaceSnapshot,
    *,
    target_key: str = "target-a",
) -> RestoreProjectionArtifact:
    """Build a minimal valid restore projection artifact for tests."""

    node = CachedNodeProjection(
        node_name="Prompt",
        node_class="CLIPTextEncode",
        field_order=("text",),
        resolved_field_specs={"text": {"field_type": "STRING"}},
        resolved_card_visibility={"visible": True},
        prompt_field_metadata={"text": {"feature_profile": "profile-fp"}},
    )
    section = CachedEditorSectionProjection(
        section_key="Scene",
        buffer_fingerprint=fingerprint_json(
            workspace.workflows[0].workflow.cubes["Scene"].buffer
        ),
        node_classes=("CLIPTextEncode",),
        node_definition_fingerprint_by_class={"CLIPTextEncode": "node-fp"},
        projected_node_order=("Prompt",),
        resolved_field_specs={"Prompt": {"text": {"field_type": "STRING"}}},
        resolved_card_visibility={"Prompt": {"visible": True}},
        field_order={"Prompt": ("text",)},
        prompt_field_metadata={"Prompt": {"text": {"syntax": "default"}}},
        nodes=(node,),
    )
    cube = CachedCubeProjection(
        requested_cube_id="cube.scene",
        canonical_cube_id="cube.scene",
        cube_version="1.0.0",
        content_hash="hash",
        catalog_revision="rev",
        section=section,
    )
    workflow = CachedWorkflowProjection(
        workflow_id="workflow-a",
        tab_label="Workflow A",
        document_kind=workspace.workflows[0].workflow.document_kind,
        workflow_fingerprint=fingerprint_json({"workflow_id": "workflow-a"}),
        cube_stack=CachedCubeStackProjection(
            stack_order=("Scene",),
            active_cube_alias="Scene",
            cubes=(cube,),
        ),
    )
    return RestoreProjectionArtifact(
        schema_version=RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
        created_at="2026-05-10T00:00:00Z",
        target_key=target_key,
        workspace_fingerprint=workspace_projection_fingerprint(workspace),
        active_route=workspace.active_route,
        active_workflow_id=workspace.active_workflow_id,
        workflows=(workflow,),
        node_definition_fingerprints={"CLIPTextEncode": "node-fp"},
        cube_definition_fingerprints={"workflow-a:Scene": "cube-fp"},
        projection={"mode": "live"},
    )


def _workspace(*, prompt_text: str = "hello") -> WorkspaceSnapshot:
    """Build one deterministic workspace snapshot for cache validation tests."""

    cube = CubeState(
        cube_id="cube.scene",
        version="1.0.0",
        alias="Scene",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "Prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": prompt_text},
                }
            }
        },
        display_name="Scene",
    )
    workflow = WorkflowState(
        cubes={"Scene": cube},
        stack_order=["Scene"],
        global_overrides={"seed": {"value": 1}},
    )
    return WorkspaceSnapshot(
        schema_version="1",
        workflows=(
            WorkflowSnapshot(
                workflow_id="workflow-a",
                tab_label="Workflow A",
                workflow=workflow,
                active_cube_alias="Scene",
            ),
        ),
        tab_order=("workflow-a",),
        active_route="editor",
        active_workflow_id="workflow-a",
    )


def _direct_workspace(*, seed: int, expanded: bool) -> WorkspaceSnapshot:
    """Build one deterministic direct-workflow snapshot."""

    direct = DirectWorkflowState(
        source_path=Path("workflows/direct.json"),
        source_workflow={"nodes": {}},
        buffer={
            "nodes": {
                "1": {
                    "class_type": "KSampler",
                    "inputs": {"seed": seed},
                    "mode": 0,
                }
            }
        },
        ui={"expanded": {"1": expanded}},
        dirty=True,
    )
    return WorkspaceSnapshot(
        schema_version="1",
        workflows=(
            WorkflowSnapshot(
                workflow_id="direct",
                tab_label="Direct",
                workflow=WorkflowState(direct_workflow=direct),
            ),
        ),
        tab_order=("direct",),
        active_route="direct",
        active_workflow_id="direct",
    )
