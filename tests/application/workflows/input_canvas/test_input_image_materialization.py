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
    _image_buffer_path,
    _workflow_input_service,
    _input_canvas_plan_service,
)


def test_materialize_input_image_updates_load_image_asset_ref(
    tmp_path: Path,
) -> None:
    """Image materialization should own the LoadImage graph association."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = _build_workflow("")
    expected_mask = tmp_path / "Recipe" / "masks" / "selected__bound.png"
    created_destinations: list[Path] = []
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id, mask_id=mask_id
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=expected_mask,
        created_destinations=created_destinations,
    )
    service = _workflow_input_service(input_canvas_state_service, canvas_io_service)

    result = service.materialize_input_image(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        cube_alias="CubeA",
        image_node_name="input_image",
        image_path="E:/images/selected.png",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert result.image_id == image_id
    assert _image_buffer_path(workflow) == str(Path("E:/images/selected.png"))
    assert input_canvas_state_service.loaded_images == [
        ("CubeA:input_image", Path("E:/images/selected.png"))
    ]


def test_materialize_input_image_hydrates_existing_expected_mask_file(
    tmp_path: Path,
) -> None:
    """Existing input-image-bound masks should hydrate when dimensions match."""

    image_id = uuid4()
    mask_id = uuid4()
    existing_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"
    existing_mask.parent.mkdir(parents=True, exist_ok=True)
    existing_mask.write_bytes(b"mask")
    workflow = _build_workflow("")
    created_destinations: list[Path] = []
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id, mask_id=mask_id
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=existing_mask,
        dimensions_by_path={existing_mask: (640, 480)},
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
        image_path="E:/images/input.png",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert result.image_id == image_id
    assert [mask_result.source for mask_result in result.mask_results] == [
        "existing_file"
    ]
    assert input_canvas_state_service.loaded_masks == [
        (("CubeA", "input_mask"), existing_mask)
    ]
    assert input_canvas_state_service.created_masks == []
    assert created_destinations == []
    assert _mask_buffer_path(workflow) == existing_mask.name


def test_materialize_input_image_creates_input_bound_blank_mask_and_updates_buffer(
    tmp_path: Path,
) -> None:
    """Missing bound masks should create a canonical blank mask and persist it."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = _build_workflow("")
    created_destinations: list[Path] = []
    expected_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"

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
        image_path="E:/images/input.png",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert result.image_id == image_id
    assert [mask_result.source for mask_result in result.mask_results] == [
        "blank_created"
    ]
    assert created_destinations == [expected_mask]
    assert _mask_buffer_path(workflow) == expected_mask.name


def test_materialize_input_image_ignores_stale_previous_mask_path(
    tmp_path: Path,
) -> None:
    """A previous input image's mask path should not hydrate for a new input image."""

    image_id = uuid4()
    mask_id = uuid4()
    stale_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"
    stale_mask.parent.mkdir(parents=True, exist_ok=True)
    stale_mask.write_bytes(b"old cat mask")
    expected_dog_mask = tmp_path / "Recipe" / "masks" / "dog__bound.png"
    workflow = _build_workflow(str(stale_mask))
    created_destinations: list[Path] = []

    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id, mask_id=mask_id
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=expected_dog_mask,
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
        image_path="E:/images/dog.png",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert result.image_id == image_id
    assert input_canvas_state_service.loaded_masks == []
    assert input_canvas_state_service.created_masks == [
        (("CubeA", "input_mask"), canvas_io_service._image.size())
    ]
    assert created_destinations == [expected_dog_mask]
    assert _mask_buffer_path(workflow) == expected_dog_mask.name
