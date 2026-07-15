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

"""Contract tests for domain workflow model invariants."""

from __future__ import annotations

import uuid

from substitute.domain.workflow import (
    CubeState,
    ImageMeta,
    OutputCompareSelection,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)


def test_cube_state_mutable_defaults_are_instance_isolated() -> None:
    """Keep undo/redo default collections isolated per cube instance."""
    first = CubeState(
        cube_id="CubeA",
        version="1.0.0",
        alias="A",
        original_cube={"nodes": {}},
        buffer={"nodes": {}},
    )
    second = CubeState(
        cube_id="CubeB",
        version="1.0.0",
        alias="B",
        original_cube={"nodes": {}},
        buffer={"nodes": {}},
    )

    first.undo_stack.append({"step": 1})
    first.redo_stack.append({"step": 2})

    assert second.undo_stack == []
    assert second.redo_stack == []
    assert first.display_name == "CubeA"
    assert second.display_name == "CubeB"


def test_workflow_state_runtime_maps_are_instance_isolated() -> None:
    """Keep workflow runtime image/mask maps isolated across workflow instances."""
    first = WorkflowState()
    second = WorkflowState()
    image_uuid = uuid.uuid4()
    mask_uuid = uuid.uuid4()

    first.canvas.input_key_map["A:input"] = image_uuid
    first.canvas.mask_associations[("A", "mask")] = mask_uuid
    first.output_image_uuids.append(image_uuid)

    assert second.canvas.input_key_map == {}
    assert second.canvas.mask_associations == {}
    assert second.output_image_uuids == []
    assert second.output_focus_mode is OutputFocusMode.AUTOMATIC
    assert second.active_output_set_index == 1
    assert second.active_output_source_key is None
    assert second.active_output_scene_key is None
    assert second.active_output_scene_overview is False
    assert second.output_compare_state == OutputCompareState()

    first.output_compare_state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
    )

    assert second.output_compare_state == OutputCompareState()


def test_image_meta_keeps_generation_context_fields() -> None:
    """Store image metadata fields used by output routing and labels."""
    meta = ImageMeta(
        workflow_name="Workflow A",
        cube_name="Cube X",
        image_number=7,
        suffix="_preview",
        path="E:/images/output.png",
        node_id="save-node",
    )

    assert meta.workflow_name == "Workflow A"
    assert meta.cube_name == "Cube X"
    assert meta.image_number == 7
    assert meta.suffix == "_preview"
    assert meta.path == "E:/images/output.png"
    assert meta.source_key == ""
    assert meta.source_label == "Cube X"
    assert meta.node_id == "save-node"
