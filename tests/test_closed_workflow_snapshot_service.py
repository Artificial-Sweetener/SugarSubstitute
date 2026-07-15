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

"""Tests for closed workflow snapshot serialization."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from substitute.application.workflows import (
    ClosedWorkflowSnapshotError,
    ClosedWorkflowSnapshotService,
)
from substitute.domain.cube_library import CubeUpdatePolicy
from substitute.domain.workflow import (
    CubeState,
    OutputCompareSelection,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    ImageMetaSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    WorkflowSnapshot,
)


def test_closed_workflow_snapshot_round_trips_workflow_state() -> None:
    """Closed workflow snapshots should preserve session-level workflow state."""

    input_id = uuid4()
    mask_id = uuid4()
    output_id = uuid4()
    workflow = WorkflowState(
        cubes={
            "Demo": CubeState(
                cube_id="owner/repo/demo.cube",
                version="1.2.3",
                alias="Demo",
                original_cube={"nodes": {"loader": {"class_type": "LoadImage"}}},
                buffer={"seed": 42, "prompt": "hello"},
                undo_stack=[{"seed": 1}],
                redo_stack=[{"seed": 2}],
                dirty=True,
                ui={"panel": {"expanded": True}},
                update_policy=CubeUpdatePolicy.PINNED,
                bypassed=True,
            )
        },
        stack_order=["Demo"],
        metadata={"title": "Closed Workflow"},
        global_overrides={"model": {"value": "demo.safetensors"}},
        global_override_selections={"model": True},
        output_image_uuids=[output_id],
        output_focus_mode=OutputFocusMode.MANUAL,
        active_output_uuid=output_id,
        active_output_set_index=2,
        active_output_source_key="Demo.Output",
        active_output_scene_key="scene-a",
        active_output_scene_overview=True,
        output_compare_state=OutputCompareState(
            enabled=True,
            base=OutputCompareSelection(
                scene_key="scene-a",
                set_index=1,
                source_key="Demo.A",
            ),
            comparison=OutputCompareSelection(
                scene_key="scene-a",
                set_index=2,
                source_key="Demo.B",
            ),
            split_position=0.25,
            orientation="horizontal",
        ),
    )
    workflow.canvas.input_key_map["Demo.LoadImage.image"] = input_id
    workflow.canvas.mask_associations[("Demo", "mask")] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = input_id
    workflow.canvas.input_image_uuid = input_id
    workflow.canvas.active_input_mask_uuid = mask_id
    workflow.canvas.active_canvas_route = "Input"
    snapshot = WorkflowSnapshot(
        workflow_id="wf-closed",
        tab_label="Closed Workflow",
        workflow=workflow,
        active_cube_alias="Demo",
        input_images=(
            InputImageReference(
                image_id=str(input_id),
                path=Path("user/inputs/demo.png"),
                sequence=0,
            ),
        ),
        input_masks=(
            InputMaskReference(
                mask_id=str(mask_id),
                image_id=str(input_id),
                path=Path("user/masks/demo-mask.png"),
                association_key=("Demo", "mask"),
            ),
        ),
        output_images=(
            OutputImageReference(
                image_id=str(output_id),
                path=Path("user/outputs/demo.png"),
                metadata=ImageMetaSnapshot(
                    workflow_name="Closed Workflow",
                    cube_name="Demo",
                    image_number=1,
                    suffix="output",
                    path=Path("user/outputs/demo.png"),
                    source_key="Demo.Output",
                    source_label="Output",
                    node_id="9",
                    width=1024,
                    height=768,
                ),
                sequence=0,
            ),
        ),
        editor_viewport=EditorViewportSnapshot(
            scroll_value=120,
            scroll_maximum=400,
            anchor_cube_alias="Demo",
        ),
    )
    service = ClosedWorkflowSnapshotService()

    restored = service.decode(service.encode(snapshot))

    assert restored.workflow_id == "wf-closed"
    assert restored.tab_label == "Closed Workflow"
    assert restored.active_cube_alias == "Demo"
    assert restored.editor_viewport == snapshot.editor_viewport
    assert restored.input_images == snapshot.input_images
    assert restored.input_masks == snapshot.input_masks
    assert restored.output_images == snapshot.output_images
    restored_workflow = restored.workflow
    assert restored_workflow.stack_order == ["Demo"]
    assert restored_workflow.cubes["Demo"].buffer == {"seed": 42, "prompt": "hello"}
    assert restored_workflow.cubes["Demo"].undo_stack == [{"seed": 1}]
    assert restored_workflow.cubes["Demo"].redo_stack == [{"seed": 2}]
    assert restored_workflow.cubes["Demo"].dirty is True
    assert restored_workflow.cubes["Demo"].bypassed is True
    assert restored_workflow.canvas.input_image_uuid == input_id
    assert restored_workflow.canvas.active_input_mask_uuid == mask_id
    assert restored_workflow.output_image_uuids == [output_id]
    assert restored_workflow.output_focus_mode == OutputFocusMode.MANUAL
    assert restored_workflow.output_compare_state == workflow.output_compare_state


def test_closed_workflow_snapshot_excludes_runtime_node_behavior() -> None:
    """Closed workflow payloads should not retain runtime-only UI collaborators."""

    snapshot = WorkflowSnapshot(
        workflow_id="wf",
        tab_label="Workflow",
        workflow=WorkflowState(
            cubes={
                "Demo": CubeState(
                    cube_id="demo",
                    version="1",
                    alias="Demo",
                    original_cube={},
                    buffer={},
                    ui={
                        "node_behavior_runtime": object(),
                        "persistent": "kept",
                    },
                )
            },
            stack_order=["Demo"],
        ),
    )

    payload = ClosedWorkflowSnapshotService().encode(snapshot)

    assert b"node_behavior_runtime" not in payload
    assert b"persistent" in payload


def test_rekey_snapshot_changes_workflow_id_only() -> None:
    """Re-keying a snapshot should leave workflow content stable."""

    snapshot = WorkflowSnapshot(
        workflow_id="wf",
        tab_label="Workflow",
        workflow=WorkflowState(
            cubes={
                "Demo": CubeState(
                    cube_id="demo",
                    version="1",
                    alias="Demo",
                    original_cube={},
                    buffer={"value": 1},
                )
            },
            stack_order=["Demo"],
        ),
    )

    rekeyed = ClosedWorkflowSnapshotService().rekey_snapshot(
        snapshot,
        new_workflow_id="wf-2",
    )

    assert rekeyed.workflow_id == "wf-2"
    assert rekeyed.tab_label == snapshot.tab_label
    assert rekeyed.workflow is snapshot.workflow
    assert rekeyed.workflow.stack_order == ["Demo"]


def test_decode_invalid_payload_fails_narrowly() -> None:
    """Invalid closed workflow payloads should fail with a snapshot error."""

    with pytest.raises(ClosedWorkflowSnapshotError):
        ClosedWorkflowSnapshotService().decode(b"not json")
