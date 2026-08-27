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

"""Verify workflow Input-canvas capability behavior."""

from __future__ import annotations

from pathlib import Path
from substitute.application.workflows import (
    WorkflowAssetService,
    WorkflowInputCanvasService,
)
from uuid import uuid4

from tests.application.workflows.input_canvas.fakes import (
    _FakeImage,
    _FakeInputCanvasStateService,
    _FakeCanvasIoService,
)
from tests.application.workflows.input_canvas.support import (
    _build_workflow,
    _mask_buffer_path,
    _workflow_input_service,
    _input_canvas_plan_service,
)


def test_apply_user_selected_input_mask_rejects_wrong_size_before_mutation(
    tmp_path: Path,
) -> None:
    """Wrong-size selected masks should not update pixels or workflow assets."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = _build_workflow("old-mask.png")
    workflow.canvas.bind_image("CubeA:input_image", image_id)
    workflow.canvas.bind_mask(("CubeA", "input_mask"), mask_id, image_id)
    selected_mask = tmp_path / "wrong-size.png"
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id,
        mask_id=mask_id,
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=tmp_path / "expected.png",
        dimensions_by_path={
            Path("E:/images/input.png"): (640, 480),
            selected_mask: (320, 240),
        },
        created_destinations=[],
    )
    service = WorkflowInputCanvasService(
        input_canvas_plan_service=_input_canvas_plan_service(),
        input_canvas_state_service=input_canvas_state_service,
        canvas_io_service=canvas_io_service,
        workflow_asset_service=WorkflowAssetService(),
    )

    result = service.apply_user_selected_input_mask(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        cube_alias="CubeA",
        mask_node_name="input_mask",
        mask_path=str(selected_mask),
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert result.applied is False
    assert result.rejection_reason == "dimension_mismatch"
    assert result.selected_dimensions == (320, 240)
    assert result.required_dimensions == (640, 480)
    assert input_canvas_state_service.updated_masks == []
    assert _mask_buffer_path(workflow) == "old-mask.png"
    assert "asset_refs" not in workflow.metadata


def test_apply_user_selected_input_mask_rejects_unverified_dimensions_before_mutation(
    tmp_path: Path,
) -> None:
    """Unverified selected masks should not update pixels or workflow assets."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = _build_workflow("old-mask.png")
    workflow.canvas.bind_image("CubeA:input_image", image_id)
    workflow.canvas.bind_mask(("CubeA", "input_mask"), mask_id, image_id)
    selected_mask = tmp_path / "unknown-size.png"
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id,
        mask_id=mask_id,
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=tmp_path / "expected.png",
        dimensions_by_path={
            Path("E:/images/input.png"): (640, 480),
            selected_mask: None,
        },
        created_destinations=[],
    )
    service = WorkflowInputCanvasService(
        input_canvas_plan_service=_input_canvas_plan_service(),
        input_canvas_state_service=input_canvas_state_service,
        canvas_io_service=canvas_io_service,
        workflow_asset_service=WorkflowAssetService(),
    )

    result = service.apply_user_selected_input_mask(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        cube_alias="CubeA",
        mask_node_name="input_mask",
        mask_path=str(selected_mask),
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert result.applied is False
    assert result.rejection_reason == "unverified_dimensions"
    assert result.selected_dimensions is None
    assert result.required_dimensions == (640, 480)
    assert input_canvas_state_service.updated_masks == []
    assert _mask_buffer_path(workflow) == "old-mask.png"
    assert "asset_refs" not in workflow.metadata


def test_materialize_input_image_creates_multiple_bound_masks(
    tmp_path: Path,
) -> None:
    """One LoadImage should materialize every graph-bound LoadImageMask node."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = _build_workflow("")
    nodes = workflow.cubes["CubeA"].buffer["nodes"]
    assert isinstance(nodes, dict)
    nodes["input_mask_b"] = {
        "class_type": "LoadImageMask",
        "inputs": {"image": ""},
    }
    consumer = nodes["consumer"]
    assert isinstance(consumer, dict)
    inputs = consumer["inputs"]
    assert isinstance(inputs, dict)
    inputs["mask_b"] = ["input_mask_b", 0]
    expected_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"
    created_destinations: list[Path] = []
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id, mask_id=mask_id
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=expected_mask,
        created_destinations=created_destinations,
    )
    service = WorkflowInputCanvasService(
        input_canvas_plan_service=_input_canvas_plan_service(),
        input_canvas_state_service=input_canvas_state_service,
        canvas_io_service=canvas_io_service,
    )

    result = service.materialize_input_image(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        cube_alias="CubeA",
        image_node_name="input_image",
        image_path="E:/images/cat.png",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert [mask_result.association_key for mask_result in result.mask_results] == [
        ("CubeA", "input_mask"),
        ("CubeA", "input_mask_b"),
    ]
    assert input_canvas_state_service.created_masks == [
        (("CubeA", "input_mask"), canvas_io_service._image.size()),
        (("CubeA", "input_mask_b"), canvas_io_service._image.size()),
    ]


def test_materialize_input_image_drops_ambiguous_mask_binding(
    tmp_path: Path,
) -> None:
    """Ambiguous editable mask bindings should not materialize by guessing."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = _build_workflow("")
    nodes = workflow.cubes["CubeA"].buffer["nodes"]
    assert isinstance(nodes, dict)
    nodes["second_image"] = {
        "class_type": "LoadImage",
        "inputs": {"image": "E:/images/second.png"},
    }
    nodes["second_consumer"] = {
        "class_type": "Blend",
        "inputs": {
            "image": ["second_image", 0],
            "mask": ["input_mask", 0],
        },
    }
    created_destinations: list[Path] = []
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id, mask_id=mask_id
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=tmp_path / "Recipe" / "masks" / "cat__bound.png",
        created_destinations=created_destinations,
    )

    result = _workflow_input_service(
        input_canvas_state_service,
        canvas_io_service,
    ).materialize_input_image(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        cube_alias="CubeA",
        image_node_name="input_image",
        image_path="E:/images/cat.png",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert result.image_id == image_id
    assert result.mask_results == ()
    assert input_canvas_state_service.loaded_masks == []
    assert input_canvas_state_service.created_masks == []
    assert created_destinations == []
