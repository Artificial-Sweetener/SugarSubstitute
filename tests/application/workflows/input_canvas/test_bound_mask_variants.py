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


def test_materialize_input_image_switching_back_reuses_compatible_bound_mask(
    tmp_path: Path,
) -> None:
    """Returning to an old input should hydrate that input's compatible mask."""

    image_id = uuid4()
    mask_id = uuid4()
    dog_mask = tmp_path / "Recipe" / "masks" / "dog__bound.png"
    cat_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"
    cat_mask.parent.mkdir(parents=True, exist_ok=True)
    cat_mask.write_bytes(b"cat mask")
    workflow = _build_workflow(str(dog_mask))
    created_destinations: list[Path] = []

    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id, mask_id=mask_id
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=cat_mask,
        dimensions_by_path={cat_mask: (640, 480)},
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

    assert result.image_id == image_id
    assert input_canvas_state_service.loaded_masks == [
        (("CubeA", "input_mask"), cat_mask)
    ]
    assert created_destinations == []
    assert _mask_buffer_path(workflow) == cat_mask.name


def test_materialize_input_image_replaces_mismatched_expected_mask_with_blank(
    tmp_path: Path,
) -> None:
    """Wrong-size expected masks should not hydrate silently."""

    image_id = uuid4()
    mask_id = uuid4()
    expected_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"
    replacement_mask = tmp_path / "Recipe" / "masks" / "cat__bound__v02.png"
    expected_mask.parent.mkdir(parents=True, exist_ok=True)
    expected_mask.write_bytes(b"wrong size")
    workflow = _build_workflow(str(expected_mask))
    created_destinations: list[Path] = []

    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id, mask_id=mask_id
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=expected_mask,
        allocated_mask_path=replacement_mask,
        dimensions_by_path={expected_mask: (1, 1)},
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

    assert result.image_id == image_id
    assert input_canvas_state_service.loaded_masks == []
    assert created_destinations == [replacement_mask]
    assert _mask_buffer_path(workflow) == replacement_mask.name


def test_materialize_input_image_reuses_compatible_variant_after_mismatch(
    tmp_path: Path,
) -> None:
    """A prior compatible replacement mask should survive later sessions."""

    image_id = uuid4()
    mask_id = uuid4()
    expected_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"
    compatible_variant = tmp_path / "Recipe" / "masks" / "cat__bound__v02.png"
    next_variant = tmp_path / "Recipe" / "masks" / "cat__bound__v03.png"
    expected_mask.parent.mkdir(parents=True, exist_ok=True)
    expected_mask.write_bytes(b"wrong size")
    compatible_variant.write_bytes(b"painted compatible mask")
    workflow = _build_workflow(str(compatible_variant))
    created_destinations: list[Path] = []

    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id, mask_id=mask_id
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=expected_mask,
        allocated_mask_path=next_variant,
        dimensions_by_path={
            expected_mask: (1, 1),
            compatible_variant: (640, 480),
        },
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

    assert result.image_id == image_id
    assert input_canvas_state_service.loaded_masks == [
        (("CubeA", "input_mask"), compatible_variant)
    ]
    assert created_destinations == []
    assert _mask_buffer_path(workflow) == compatible_variant.name


def test_materialize_input_image_replaces_wrong_size_previous_variant(
    tmp_path: Path,
) -> None:
    """Wrong-size previous variants should be replaced with a compatible blank."""

    image_id = uuid4()
    mask_id = uuid4()
    expected_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"
    previous_variant = tmp_path / "Recipe" / "masks" / "cat__bound__v02.png"
    previous_variant.parent.mkdir(parents=True, exist_ok=True)
    previous_variant.write_bytes(b"wrong previous")
    workflow = _build_workflow(str(previous_variant))
    created_destinations: list[Path] = []

    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id, mask_id=mask_id
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=expected_mask,
        dimensions_by_path={previous_variant: (1, 1)},
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
    assert input_canvas_state_service.loaded_masks == []
    assert created_destinations == [expected_mask]
    assert _mask_buffer_path(workflow) == expected_mask.name


def test_materialize_input_image_preserves_explicit_manual_mask_asset(
    tmp_path: Path,
) -> None:
    """Compatible user-selected mask assets should win over generated paths."""

    image_id = uuid4()
    mask_id = uuid4()
    selected_mask = tmp_path / "manual-mask.png"
    expected_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"
    selected_mask.write_bytes(b"manual mask")
    expected_mask.parent.mkdir(parents=True, exist_ok=True)
    expected_mask.write_bytes(b"generated mask")
    workflow = _build_workflow("")
    asset_service = WorkflowAssetService()
    assert asset_service.associate_local_input_mask(
        workflow,
        section_key="CubeA",
        node_name="input_mask",
        field_key="image",
        mask_path=selected_mask,
    )
    created_destinations: list[Path] = []
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id, mask_id=mask_id
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=expected_mask,
        dimensions_by_path={
            selected_mask: (640, 480),
            expected_mask: (640, 480),
        },
        created_destinations=created_destinations,
    )
    service = WorkflowInputCanvasService(
        input_canvas_plan_service=_input_canvas_plan_service(),
        input_canvas_state_service=input_canvas_state_service,
        canvas_io_service=canvas_io_service,
        workflow_asset_service=asset_service,
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

    assert [mask_result.source for mask_result in result.mask_results] == [
        "manual_file"
    ]
    assert input_canvas_state_service.loaded_masks == [
        (("CubeA", "input_mask"), selected_mask)
    ]
    assert created_destinations == []
    assert _mask_buffer_path(workflow) == str(selected_mask)


def test_materialize_input_image_replaces_wrong_size_explicit_manual_mask(
    tmp_path: Path,
) -> None:
    """Wrong-size user-selected mask assets should not hydrate into QPane."""

    image_id = uuid4()
    mask_id = uuid4()
    selected_mask = tmp_path / "manual-mask.png"
    expected_mask = tmp_path / "Recipe" / "masks" / "cat__bound.png"
    selected_mask.write_bytes(b"wrong manual mask")
    workflow = _build_workflow("")
    asset_service = WorkflowAssetService()
    assert asset_service.associate_local_input_mask(
        workflow,
        section_key="CubeA",
        node_name="input_mask",
        field_key="image",
        mask_path=selected_mask,
    )
    created_destinations: list[Path] = []
    input_canvas_state_service = _FakeInputCanvasStateService(
        image_id=image_id, mask_id=mask_id
    )
    canvas_io_service = _FakeCanvasIoService(
        image=_FakeImage(),
        expected_mask_path=expected_mask,
        dimensions_by_path={selected_mask: (320, 240)},
        created_destinations=created_destinations,
    )
    service = WorkflowInputCanvasService(
        input_canvas_plan_service=_input_canvas_plan_service(),
        input_canvas_state_service=input_canvas_state_service,
        canvas_io_service=canvas_io_service,
        workflow_asset_service=asset_service,
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

    assert [mask_result.source for mask_result in result.mask_results] == [
        "blank_created"
    ]
    assert input_canvas_state_service.loaded_masks == []
    assert created_destinations == [expected_mask]
    assert _mask_buffer_path(workflow) == expected_mask.name
