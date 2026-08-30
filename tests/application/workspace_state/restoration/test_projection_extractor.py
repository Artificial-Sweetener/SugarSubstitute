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

"""Tests for extracting live restored editor projection cache artifacts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.application.workflows import DIRECT_WORKFLOW_SECTION_KEY
from substitute.application.workspace_state.restore_projection_codec import (
    restore_projection_artifact_from_json,
    restore_projection_artifact_to_json,
)
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot
from substitute.application.workspace_state.restored_editor_projection import (
    RestoredEditorProjectionCacheExtractor,
)


def test_restored_editor_projection_extractor_captures_qt_free_artifact() -> None:
    """Extraction should produce serializable cache data from live restored state."""

    snapshot = _workspace()
    panel = SimpleNamespace(
        _last_behavior_snapshot=SimpleNamespace(
            field_specs_by_alias={
                "Scene": {
                    "Prompt": {
                        "text": SimpleNamespace(
                            cube_alias="Scene",
                            node_name="Prompt",
                            class_type="CLIPTextEncode",
                            field_key="text",
                            field_type="STRING",
                            constraints={"multiline": True},
                            field_info=["STRING", {"default": ""}],
                            value_source="explicit",
                            field_behavior=SimpleNamespace(
                                presentation="prompt_box",
                                control_name="",
                                label_override="",
                                style={"prompt_syntaxes": ["default"]},
                            ),
                        )
                    }
                }
            },
            card_decisions_by_alias={"Scene": {"Prompt": {"visible": True}}},
        )
    )
    gateway = _NodeDefinitionGateway(
        {"CLIPTextEncode": {"input": {"required": {"text": ["STRING", {}]}}}}
    )

    artifact = RestoredEditorProjectionCacheExtractor().capture(
        snapshot=snapshot,
        target_key="target",
        editor_panels={"workflow-a": panel},
        node_definition_gateway=gateway,
    )

    restore_projection_artifact_from_json(restore_projection_artifact_to_json(artifact))
    assert artifact.target_key == "target"
    assert artifact.active_workflow_id == "workflow-a"
    assert artifact.cube_definition_fingerprints.keys() == {"workflow-a:Scene"}
    assert artifact.node_definition_fingerprints.keys() == {"CLIPTextEncode"}
    cube_stack = artifact.workflows[0].cube_stack
    assert cube_stack is not None
    cube = cube_stack.cubes[0]
    assert cube.alias == "Scene"
    assert cube.section.projected_node_order == ("Prompt",)
    assert cube.section.field_order == {"Prompt": ("text",)}
    assert cube.section.prompt_field_metadata == {
        "Prompt": {
            "text": {
                "field_type": "STRING",
                "style": {"prompt_syntaxes": ["default"]},
            }
        }
    }


def test_restored_editor_projection_extractor_captures_direct_document() -> None:
    """Direct documents should use the shared section and node-definition cache."""

    snapshot = _direct_workspace()
    panel = SimpleNamespace(
        _last_behavior_snapshot=SimpleNamespace(
            field_specs_by_alias={
                DIRECT_WORKFLOW_SECTION_KEY: {
                    "1": {
                        "seed": SimpleNamespace(
                            cube_alias=DIRECT_WORKFLOW_SECTION_KEY,
                            node_name="1",
                            class_type="KSampler",
                            field_key="seed",
                            field_type="INT",
                            constraints={"min": 0, "max": 100},
                            field_info=["INT", {"default": 0}],
                            value_source="explicit",
                            field_behavior=SimpleNamespace(
                                presentation="seed_box",
                                control_name="seed",
                                label_override="",
                                style={},
                            ),
                        )
                    }
                }
            },
            card_decisions_by_alias={
                DIRECT_WORKFLOW_SECTION_KEY: {"1": {"visible": True}}
            },
        )
    )
    gateway = _NodeDefinitionGateway(
        {"KSampler": {"input": {"required": {"seed": ["INT", {}]}}}}
    )

    artifact = RestoredEditorProjectionCacheExtractor().capture(
        snapshot=snapshot,
        target_key="target",
        editor_panels={"direct": panel},
        node_definition_gateway=gateway,
    )

    restore_projection_artifact_from_json(restore_projection_artifact_to_json(artifact))
    cached = artifact.workflows[0]
    assert cached.cube_stack is None
    assert cached.direct_workflow is not None
    assert cached.direct_workflow.section.section_key == DIRECT_WORKFLOW_SECTION_KEY
    assert cached.direct_workflow.section.projected_node_order == ("1",)
    assert cached.direct_workflow.section.field_order == {"1": ("seed",)}
    assert artifact.node_definition_fingerprints.keys() == {"KSampler"}
    assert artifact.cube_definition_fingerprints == {}


class _NodeDefinitionGateway:
    """Node definition gateway test double."""

    def __init__(self, definitions: dict[str, dict[str, object]]) -> None:
        """Store definitions keyed by node class."""

        self._definitions = definitions

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the configured node definition payload."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the configured required node definition payload."""

        return self._definitions.get(node_class, {})


def _workspace() -> WorkspaceSnapshot:
    """Build one hydrated workspace snapshot with cube identity metadata."""

    cube = CubeState(
        cube_id="cube.scene",
        version="1.0.0",
        alias="Scene",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "Prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "hello"},
                }
            }
        },
        display_name="Scene",
        ui={
            "content_hash": "hash",
            "catalog_revision": "rev",
            "canonical_cube": {"cube_id": "cube.scene"},
        },
    )
    return WorkspaceSnapshot(
        schema_version="1",
        workflows=(
            WorkflowSnapshot(
                workflow_id="workflow-a",
                tab_label="Workflow A",
                workflow=WorkflowState(
                    cubes={"Scene": cube},
                    stack_order=["Scene"],
                ),
                active_cube_alias="Scene",
            ),
        ),
        tab_order=("workflow-a",),
        active_route="editor",
        active_workflow_id="workflow-a",
    )


def _direct_workspace() -> WorkspaceSnapshot:
    """Build one direct workflow for projection extraction."""

    direct = DirectWorkflowState(
        source_path=Path("workflows/direct.json"),
        source_workflow={"nodes": {}},
        buffer={
            "nodes": {
                "1": {
                    "class_type": "KSampler",
                    "inputs": {"seed": 7},
                    "mode": 0,
                }
            }
        },
        ui={"expanded": {"1": True}},
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
