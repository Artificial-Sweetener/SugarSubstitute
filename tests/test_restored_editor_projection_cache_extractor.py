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

from types import SimpleNamespace

from substitute.application.workspace_state import RestoreProjectionArtifact
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

    RestoreProjectionArtifact.from_json(artifact.to_json())
    assert artifact.target_key == "target"
    assert artifact.active_workflow_id == "workflow-a"
    assert artifact.cube_definition_fingerprints.keys() == {"Scene"}
    assert artifact.node_definition_fingerprints.keys() == {"CLIPTextEncode"}
    cube = artifact.workflows[0].cubes[0]
    assert cube.alias == "Scene"
    assert cube.projected_node_order == ("Prompt",)
    assert cube.field_order == {"Prompt": ("text",)}
    assert cube.prompt_field_metadata == {
        "Prompt": {
            "text": {
                "field_type": "STRING",
                "style": {"prompt_syntaxes": ["default"]},
            }
        }
    }


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
