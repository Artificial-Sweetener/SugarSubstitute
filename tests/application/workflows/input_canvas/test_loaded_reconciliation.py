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
    _workflow_input_service,
    _input_canvas_plan_service,
)


def test_reconcile_loaded_input_canvas_image_preserves_existing_image_uuid(
    tmp_path: Path,
) -> None:
    """Input-canvas loads should reuse the QPane image UUID and only add masks."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = _build_workflow("")
    expected_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"
    created_destinations: list[Path] = []
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=uuid4(), mask_id=mask_id
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

    result = service.reconcile_loaded_input_canvas_image(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        cube_alias="CubeA",
        image_node_name="input_image",
        image_id=image_id,
        image_path="E:/images/cat.png",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert result.image_id == image_id
    image_entry = workflow.canvas.image_entry("CubeA:input_image")
    assert image_entry is not None
    assert image_entry.image_id == image_id
    assert workflow.canvas.input_image_uuid == image_id
    assert input_canvas_state_service.claimed_images == [
        ("CubeA:input_image", image_id)
    ]
    assert input_canvas_state_service.loaded_images == []
    assert input_canvas_state_service.active_input_images == []
    assert input_canvas_state_service.created_masks == [
        (("CubeA", "input_mask"), canvas_io_service._image.size())
    ]


def test_reconcile_loaded_input_canvas_image_reuses_existing_canvas_mask(
    tmp_path: Path,
) -> None:
    """Repeated reconciliation should not allocate duplicate mask layers."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = _build_workflow("")
    expected_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"
    created_destinations: list[Path] = []
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=uuid4(),
        mask_id=mask_id,
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

    first_result = service.reconcile_loaded_input_canvas_image(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        cube_alias="CubeA",
        image_node_name="input_image",
        image_id=image_id,
        image_path="E:/images/cat.png",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )
    second_result = service.reconcile_loaded_input_canvas_image(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        cube_alias="CubeA",
        image_node_name="input_image",
        image_id=image_id,
        image_path="E:/images/cat.png",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert [mask_result.source for mask_result in first_result.mask_results] == [
        "blank_created"
    ]
    assert [mask_result.source for mask_result in second_result.mask_results] == [
        "existing_canvas"
    ]
    assert [mask_result.mask_id for mask_result in second_result.mask_results] == [
        mask_id
    ]
    assert input_canvas_state_service.created_masks == [
        (("CubeA", "input_mask"), canvas_io_service._image.size())
    ]
    assert input_canvas_state_service.loaded_masks == []
    assert input_canvas_state_service.dropped_associations == []


def test_reconcile_loaded_input_canvas_image_drops_stale_mask_association(
    tmp_path: Path,
) -> None:
    """A mask bound to an old image should be removed before rematerializing."""

    old_image_id = uuid4()
    new_image_id = uuid4()
    old_mask_id = uuid4()
    new_mask_id = uuid4()
    workflow = _build_workflow("")
    workflow.canvas.bind_mask(
        ("CubeA", "input_mask"),
        old_mask_id,
        old_image_id,
    )
    expected_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"
    created_destinations: list[Path] = []
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=uuid4(),
        mask_id=new_mask_id,
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

    result = service.reconcile_loaded_input_canvas_image(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        cube_alias="CubeA",
        image_node_name="input_image",
        image_id=new_image_id,
        image_path="E:/images/cat.png",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert [mask_result.source for mask_result in result.mask_results] == [
        "blank_created"
    ]
    assert input_canvas_state_service.dropped_associations == [("CubeA", "input_mask")]
    mask_entry = workflow.canvas.mask_entry(("CubeA", "input_mask"))
    assert mask_entry is not None
    assert mask_entry.mask_id == new_mask_id
    assert mask_entry.image_id == new_image_id
    assert workflow.canvas.mask_entry_for_id(old_mask_id) is None


def test_reconcile_loaded_input_canvas_image_rejects_stale_workflow(
    tmp_path: Path,
) -> None:
    """Stale direct QPane load reconciliation should preserve the QPane UUID."""

    workflow = _build_workflow("")
    image_id = uuid4()
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
    ).reconcile_loaded_input_canvas_image(
        workflows={"wf-a": workflow},
        workflow_id="wf-stale",
        cube_alias="CubeA",
        image_node_name="input_image",
        image_id=image_id,
        image_path="E:/images/cat.png",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert result.image_id is None
    assert workflow.canvas.image_entries == {}
    assert input_canvas_state_service.active_input_images == []
