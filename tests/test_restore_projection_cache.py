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

"""Tests for restore projection cache models and validation policy."""

from __future__ import annotations

from dataclasses import replace

import pytest

from substitute.application.cubes import LoadedCubeDefinition
from substitute.application.workspace_state.restore_projection_cache import (
    APP_PROJECTION_VERSION,
    RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
    CachedCubeProjection,
    CachedNodeProjection,
    CachedWorkflowProjection,
    RestoreProjectionArtifact,
    RestoreProjectionCacheState,
    RestoreProjectionValidationService,
    cube_definition_fingerprint,
    fingerprint_json,
    node_definition_fingerprint,
    prompt_feature_profile_fingerprint,
    workspace_projection_fingerprint,
)
from substitute.domain.prompt import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptFeatureDecision,
)
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot


def test_restore_projection_artifact_round_trips_through_json() -> None:
    """Artifacts should serialize through the explicit durable JSON shape."""

    workspace = _workspace()
    artifact = _artifact(workspace)

    restored = RestoreProjectionArtifact.from_json(artifact.to_json())

    assert restored == artifact


def test_restore_projection_artifact_rejects_invalid_json() -> None:
    """Invalid payloads should fail before bootstrap depends on them."""

    with pytest.raises(ValueError, match="restore projection artifact"):
        RestoreProjectionArtifact.from_json([])

    payload = _artifact(_workspace()).to_json()
    payload["workflows"] = "not-a-list"

    with pytest.raises(ValueError, match="workflows"):
        RestoreProjectionArtifact.from_json(payload)


def test_restore_projection_artifact_rejects_schema_mismatch() -> None:
    """Durable cache parsing should reject incompatible schema versions."""

    payload = _artifact(_workspace()).to_json()
    payload["schema_version"] = RESTORE_PROJECTION_CACHE_SCHEMA_VERSION + 1

    with pytest.raises(ValueError, match="schema_version"):
        RestoreProjectionArtifact.from_json(payload)


def test_validate_before_backend_rejects_target_mismatch() -> None:
    """Pre-backend validation should keep caches scoped to backend target."""

    workspace = _workspace()
    artifact = _artifact(workspace, target_key="target-a")

    result = RestoreProjectionValidationService().validate_before_backend(
        artifact,
        target_key="target-b",
        workspace=workspace,
    )

    assert result.state is RestoreProjectionCacheState.TARGET_MISMATCH
    assert not result.can_build_provisionally


def test_validate_before_backend_rejects_workspace_mismatch() -> None:
    """Pre-backend validation should reject cache data for another workspace."""

    artifact = _artifact(_workspace())
    changed_workspace = _workspace(prompt_text="changed")

    result = RestoreProjectionValidationService().validate_before_backend(
        artifact,
        target_key="target-a",
        workspace=changed_workspace,
    )

    assert result.state is RestoreProjectionCacheState.WORKSPACE_MISMATCH
    assert not result.can_build_provisionally


def test_validate_before_backend_accepts_local_identity_until_backend_ready() -> None:
    """A matching artifact should become provisional, not fully valid."""

    workspace = _workspace()
    artifact = _artifact(workspace)

    result = RestoreProjectionValidationService().validate_before_backend(
        artifact,
        target_key="target-a",
        workspace=workspace,
    )

    assert result.state is RestoreProjectionCacheState.BACKEND_PENDING
    assert result.can_build_provisionally
    assert not result.is_valid


def test_validate_before_backend_rejects_qt_unsafe_numeric_cache_metadata() -> None:
    """Pre-backend validation should reject cached slider specs that overflow Qt."""

    workspace = _workspace()
    node = replace(
        _artifact(workspace).workflows[0].cubes[0].nodes[0],
        resolved_field_specs={
            "value": {
                "label": "Scale Factor",
                "min": -9_223_372_036_854_775_807,
                "max": 9_223_372_036_854_775_807,
                "step": 0.1,
            }
        },
    )
    base_artifact = _artifact(workspace)
    cube = replace(base_artifact.workflows[0].cubes[0], nodes=(node,))
    workflow = replace(base_artifact.workflows[0], cubes=(cube,))
    artifact = replace(base_artifact, workflows=(workflow,))

    result = RestoreProjectionValidationService().validate_before_backend(
        artifact,
        target_key="target-a",
        workspace=workspace,
    )

    assert result.state is RestoreProjectionCacheState.INVALID
    assert not result.can_build_provisionally
    assert "Qt-unsafe range" in result.reasons[0]


def test_workspace_projection_fingerprint_ignores_active_cube_alias() -> None:
    """Viewport-driven cube selection drift should not invalidate projection caches."""

    workspace = _workspace()
    changed_workspace = replace(
        workspace,
        workflows=(replace(workspace.workflows[0], active_cube_alias=None),),
    )

    assert workspace_projection_fingerprint(changed_workspace) == (
        workspace_projection_fingerprint(workspace)
    )


def test_workspace_projection_fingerprint_includes_cube_bypass_state() -> None:
    """Bypass changes should invalidate cached editor projections."""

    workspace = _workspace()
    changed_cube = replace(
        workspace.workflows[0].workflow.cubes["Scene"], bypassed=True
    )
    changed_workflow_state = replace(
        workspace.workflows[0].workflow,
        cubes={"Scene": changed_cube},
    )
    changed_workspace = replace(
        workspace,
        workflows=(replace(workspace.workflows[0], workflow=changed_workflow_state),),
    )

    assert workspace_projection_fingerprint(changed_workspace) != (
        workspace_projection_fingerprint(workspace)
    )


def test_validate_before_backend_accepts_active_cube_alias_drift() -> None:
    """Pre-backend validation should accept caches when only cube focus changed."""

    workspace = _workspace()
    artifact = _artifact(workspace)
    changed_workspace = replace(
        workspace,
        workflows=(replace(workspace.workflows[0], active_cube_alias=None),),
    )

    result = RestoreProjectionValidationService().validate_before_backend(
        artifact,
        target_key="target-a",
        workspace=changed_workspace,
    )

    assert result.state is RestoreProjectionCacheState.BACKEND_PENDING
    assert result.can_build_provisionally


def test_validate_before_backend_accepts_legacy_active_alias_fingerprint() -> None:
    """Old cache files should survive when only their stored cube focus differs."""

    workspace = _workspace()
    artifact = replace(
        _artifact(workspace),
        workspace_fingerprint=_legacy_workspace_projection_fingerprint(workspace),
    )
    changed_workspace = replace(
        workspace,
        workflows=(replace(workspace.workflows[0], active_cube_alias=None),),
    )

    result = RestoreProjectionValidationService().validate_before_backend(
        artifact,
        target_key="target-a",
        workspace=changed_workspace,
    )

    assert result.state is RestoreProjectionCacheState.BACKEND_PENDING
    assert result.can_build_provisionally
    assert result.reasons == (
        "Cache matches local restore identity after ignoring cube focus drift.",
    )


def test_validate_after_backend_rejects_missing_cube_fingerprint() -> None:
    """Live validation should mark absent cube identities as stale."""

    artifact = _artifact(_workspace())

    result = RestoreProjectionValidationService().validate_after_backend(
        artifact,
        live_cube_fingerprints={},
        live_node_fingerprints={"CLIPTextEncode": "node-fp"},
    )

    assert result.state is RestoreProjectionCacheState.STALE_CUBE
    assert result.stale_cube_aliases == ("Scene",)
    assert not result.is_valid


def test_validate_after_backend_rejects_stale_node_definition() -> None:
    """Live validation should identify changed node definitions exactly."""

    artifact = _artifact(_workspace())

    result = RestoreProjectionValidationService().validate_after_backend(
        artifact,
        live_cube_fingerprints={"Scene": "cube-fp"},
        live_node_fingerprints={"CLIPTextEncode": "changed"},
    )

    assert result.state is RestoreProjectionCacheState.STALE_NODE_DEFINITION
    assert result.stale_node_classes == ("CLIPTextEncode",)
    assert not result.is_valid


def test_validate_after_backend_accepts_matching_live_fingerprints() -> None:
    """Live validation should promote exact cube and node identity matches."""

    artifact = _artifact(_workspace())

    result = RestoreProjectionValidationService().validate_after_backend(
        artifact,
        live_cube_fingerprints={"Scene": "cube-fp"},
        live_node_fingerprints={"CLIPTextEncode": "node-fp"},
    )

    assert result.state is RestoreProjectionCacheState.VALID
    assert result.is_valid


def test_fingerprints_are_stable_across_key_ordering() -> None:
    """Fingerprint helpers should normalize JSON object key ordering."""

    assert fingerprint_json({"b": 2, "a": {"z": 1, "c": 3}}) == fingerprint_json(
        {"a": {"c": 3, "z": 1}, "b": 2}
    )
    assert node_definition_fingerprint({"inputs": {"b": 2, "a": 1}}) == (
        node_definition_fingerprint({"inputs": {"a": 1, "b": 2}})
    )
    assert cube_definition_fingerprint(
        LoadedCubeDefinition(
            cube_id="cube",
            version="1",
            display_name="Cube",
            graph={"nodes": {"b": 2, "a": 1}},
            ui_payload={"content_hash": "hash", "catalog_revision": "rev"},
        )
    ) == cube_definition_fingerprint(
        LoadedCubeDefinition(
            cube_id="cube",
            version="1",
            display_name="Cube",
            graph={"nodes": {"a": 1, "b": 2}},
            ui_payload={"catalog_revision": "rev", "content_hash": "hash"},
        )
    )


def test_prompt_feature_profile_fingerprint_is_order_independent() -> None:
    """Prompt feature profiles should fingerprint by feature identity."""

    first = PromptEditorFeatureProfile(
        decisions=(
            PromptFeatureDecision(PromptEditorFeature.SPELLCHECK, enabled=True),
            PromptFeatureDecision(PromptEditorFeature.EMPHASIS, enabled=False),
        )
    )
    second = PromptEditorFeatureProfile(
        decisions=(
            PromptFeatureDecision(PromptEditorFeature.EMPHASIS, enabled=False),
            PromptFeatureDecision(PromptEditorFeature.SPELLCHECK, enabled=True),
        )
    )

    assert prompt_feature_profile_fingerprint(first) == (
        prompt_feature_profile_fingerprint(second)
    )


def test_validation_reports_schema_mismatch_from_constructed_artifact() -> None:
    """Validation should handle incompatible artifacts even when already parsed."""

    workspace = _workspace()
    artifact = replace(_artifact(workspace), app_projection_version=999)

    result = RestoreProjectionValidationService().validate_before_backend(
        artifact,
        target_key="target-a",
        workspace=workspace,
    )

    assert result.state is RestoreProjectionCacheState.SCHEMA_MISMATCH


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
    cube = CachedCubeProjection(
        alias="Scene",
        requested_cube_id="cube.scene",
        canonical_cube_id="cube.scene",
        cube_version="1.0.0",
        content_hash="hash",
        catalog_revision="rev",
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
    workflow = CachedWorkflowProjection(
        workflow_id="workflow-a",
        tab_label="Workflow A",
        stack_order=("Scene",),
        active_cube_alias="Scene",
        cube_aliases=("Scene",),
        workflow_fingerprint=fingerprint_json({"workflow_id": "workflow-a"}),
        cubes=(cube,),
    )
    return RestoreProjectionArtifact(
        schema_version=RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
        created_at="2026-05-10T00:00:00Z",
        app_projection_version=APP_PROJECTION_VERSION,
        target_key=target_key,
        workspace_fingerprint=workspace_projection_fingerprint(workspace),
        active_route=workspace.active_route,
        active_workflow_id=workspace.active_workflow_id,
        workflows=(workflow,),
        prompt_editor_feature_profile_fingerprint="profile-fp",
        node_definition_fingerprints={"CLIPTextEncode": "node-fp"},
        cube_definition_fingerprints={"Scene": "cube-fp"},
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


def _legacy_workspace_projection_fingerprint(snapshot: WorkspaceSnapshot) -> str:
    """Return the previous selection-sensitive workspace cache fingerprint."""

    workflow = snapshot.workflows[0]
    cube = workflow.workflow.cubes["Scene"]
    return fingerprint_json(
        {
            "schema_version": snapshot.schema_version,
            "active_route": snapshot.active_route,
            "active_workflow_id": snapshot.active_workflow_id,
            "tab_order": list(snapshot.tab_order),
            "workflows": [
                {
                    "workflow_id": workflow.workflow_id,
                    "tab_label": workflow.tab_label,
                    "active_cube_alias": workflow.active_cube_alias,
                    "stack_order": list(workflow.workflow.stack_order),
                    "global_overrides": workflow.workflow.global_overrides,
                    "cubes": [
                        {
                            "alias": "Scene",
                            "cube_id": cube.cube_id,
                            "version": cube.version,
                            "display_name": cube.display_name,
                            "buffer_fingerprint": fingerprint_json(cube.buffer),
                        }
                    ],
                }
            ],
        }
    )
