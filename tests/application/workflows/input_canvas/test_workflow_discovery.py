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
from substitute.application.workflows.editor_projection_service import (
    DIRECT_WORKFLOW_SECTION_KEY,
)
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.common import JsonObject
from substitute.domain.workflow import WorkflowState
from typing import cast
from uuid import uuid4

from tests.application.workflows.input_canvas.fakes import (
    _FakeImage,
    _FakeInputCanvasStateService,
    _FakeCanvasIoService,
)
from tests.application.workflows.input_canvas.support import (
    _build_workflow,
    _image_buffer_path,
    _workflow_input_service,
)


def test_materialize_loaded_cube_scans_graph_bound_local_images_only(
    tmp_path: Path,
) -> None:
    """Loaded cubes should materialize editable local LoadImage bindings only."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = _build_workflow("")
    nodes = workflow.cubes["CubeA"].buffer["nodes"]
    assert isinstance(nodes, dict)
    image_node = nodes["input_image"]
    assert isinstance(image_node, dict)
    image_inputs = image_node["inputs"]
    assert isinstance(image_inputs, dict)
    image_inputs["image"] = "E:/images/bound.png"
    nodes["standalone_image"] = {
        "class_type": "LoadImage",
        "inputs": {"image": "E:/images/standalone.png"},
    }
    expected_mask = tmp_path / "Recipe" / "masks" / "bound__mask.png"
    created_destinations: list[Path] = []
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id, mask_id=mask_id
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=expected_mask,
        created_destinations=created_destinations,
    )

    results = _workflow_input_service(
        input_canvas_state_service,
        canvas_io_service,
    ).materialize_loaded_section(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        section_key="CubeA",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert [result.image_id for result in results] == [image_id]
    assert input_canvas_state_service.loaded_images == [
        ("CubeA:input_image", Path("E:/images/bound.png"))
    ]


def test_materialize_loaded_cube_ignores_non_local_image_values(
    tmp_path: Path,
) -> None:
    """Loaded-cube materialization should skip Comfy input namespace values."""

    workflow = _build_workflow("")
    nodes = workflow.cubes["CubeA"].buffer["nodes"]
    assert isinstance(nodes, dict)
    image_node = nodes["input_image"]
    assert isinstance(image_node, dict)
    image_inputs = image_node["inputs"]
    assert isinstance(image_inputs, dict)
    image_inputs["image"] = "comfy_input.png"
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=uuid4(),
        mask_id=uuid4(),
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=tmp_path / "Recipe" / "masks" / "mask.png",
        created_destinations=[],
    )

    results = _workflow_input_service(
        input_canvas_state_service,
        canvas_io_service,
    ).materialize_loaded_section(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        section_key="CubeA",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert results == ()
    assert input_canvas_state_service.loaded_images == []


def test_direct_workflow_materializes_image_and_bound_mask_through_shared_service(
    tmp_path: Path,
) -> None:
    """Direct documents should use the same image, mask, and asset lifecycle as cubes."""

    selected_image_path = Path("images/selected.png")
    graph: JsonObject = {
        "nodes": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": str(Path("images/source.png"))},
            },
            "2": {
                "class_type": "LoadImageMask",
                "inputs": {"image": ""},
            },
            "3": {
                "class_type": "Consumer",
                "inputs": {"pixels": ["1", 0], "mask": ["2", 0]},
            },
        }
    }
    direct = DirectWorkflowState(
        source_path=tmp_path / "workflow.json",
        source_workflow=graph,
        buffer=graph,
    )
    workflow = WorkflowState(direct_workflow=direct)
    image_id = uuid4()
    mask_id = uuid4()
    expected_mask = tmp_path / "Direct" / "masks" / "source__mask.png"
    input_state = _FakeInputCanvasStateService(image_id=image_id, mask_id=mask_id)
    service = _workflow_input_service(
        input_state,
        _FakeCanvasIoService(
            image=_FakeImage(),
            expected_mask_path=expected_mask,
            created_destinations=[],
        ),
    )

    result = service.materialize_input_image(
        workflows={"wf-direct": workflow},
        workflow_id="wf-direct",
        cube_alias=DIRECT_WORKFLOW_SECTION_KEY,
        image_node_name="1",
        image_path=str(selected_image_path),
        workflow_name="Direct",
        projects_dir=tmp_path,
    )

    assert result.image_id == image_id
    assert [item.mask_id for item in result.mask_results] == [mask_id]
    nodes = cast(dict[str, JsonObject], direct.buffer["nodes"])
    assert cast(JsonObject, nodes["1"]["inputs"])["image"] == str(selected_image_path)
    assert cast(JsonObject, nodes["2"]["inputs"])["image"] == expected_mask.name
    assert direct.dirty is True


def test_materialize_input_image_rejects_stale_workflow_without_graph_update(
    tmp_path: Path,
) -> None:
    """Stale workflow IDs should not write graph buffers or load canvas state."""

    workflow = _build_workflow("")
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=uuid4(),
        mask_id=uuid4(),
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=tmp_path / "Recipe" / "masks" / "mask.png",
        created_destinations=[],
    )

    result = _workflow_input_service(
        input_canvas_state_service,
        canvas_io_service,
    ).materialize_input_image(
        workflows={"wf-a": workflow},
        workflow_id="wf-stale",
        cube_alias="CubeA",
        image_node_name="input_image",
        image_path="E:/images/stale.png",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert result.image_id is None
    assert _image_buffer_path(workflow) == "E:/images/input.png"
    assert input_canvas_state_service.loaded_images == []
