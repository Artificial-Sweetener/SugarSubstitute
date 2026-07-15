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

"""Contract tests for workflow-level input canvas reconciliation."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from substitute.application.cubes import CubeMaskBindingService
from substitute.application.workflows import (
    WorkflowAssetService,
    WorkflowInputCanvasService,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState, WorkflowState


class _FakeImage:
    """Expose the small image API shape used by workflow input canvas service."""

    def __init__(self, *, null: bool = False, size_value: object | None = None) -> None:
        self._null = null
        self._size_value = size_value or _FakeSize(640, 480)

    def isNull(self) -> bool:
        """Return whether the fake image should be treated as invalid."""

        return self._null

    def size(self) -> object:
        """Return the fake image size payload."""

        return self._size_value


class _FakeSize:
    """Expose a Qt-like width and height API for image size tests."""

    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def width(self) -> int:
        """Return configured width."""

        return self._width

    def height(self) -> int:
        """Return configured height."""

        return self._height


class _FakeInputCanvasStateService:
    """Capture explicit image and mask materialization commands for assertions."""

    def __init__(self, *, image_id: UUID, mask_id: UUID) -> None:
        self._image_id = image_id
        self._mask_id = mask_id
        self.loaded_images: list[tuple[str, Path]] = []
        self.loaded_masks: list[tuple[tuple[str, str], Path]] = []
        self.created_masks: list[tuple[tuple[str, str], object]] = []
        self.dropped_associations: list[tuple[str, str]] = []
        self.active_input_images: list[UUID] = []
        self.claimed_images: list[tuple[str, UUID]] = []
        self.updated_masks: list[tuple[tuple[str, str], UUID, Path]] = []

    def load_input_image(
        self,
        workflows: object,
        active_workflow_id: str,
        input_key: str,
        image: object,
        path: Path,
    ) -> UUID:
        """Return the configured input image identifier."""

        _ = workflows, active_workflow_id, image
        self.loaded_images.append((input_key, path))
        return self._image_id

    def set_active_input_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> bool:
        """Record active image changes for existing-image reconciliation."""

        _ = workflow_id, workflow
        self.active_input_images.append(image_id)
        return True

    def claim_loaded_input_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        input_key: str,
        image_id: UUID,
    ) -> bool:
        """Claim an existing image identifier for a workflow input key."""

        _ = workflow_id
        self.claimed_images.append((input_key, image_id))
        workflow.canvas.input_key_map[input_key] = image_id
        workflow.canvas.input_image_uuid = image_id
        return True

    def load_mask_from_file(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        path: Path,
    ) -> UUID:
        """Record existing-file hydration and return the configured mask UUID."""

        _ = workflow_id
        self.loaded_masks.append((association_key, path))
        active_workflow.canvas.mask_associations[association_key] = self._mask_id
        active_workflow.canvas.mask_to_image_map[self._mask_id] = image_id
        return self._mask_id

    def create_mask_for_image(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        size: object,
    ) -> UUID:
        """Record blank-mask creation and return the configured mask UUID."""

        _ = workflow_id
        self.created_masks.append((association_key, size))
        active_workflow.canvas.mask_associations[association_key] = self._mask_id
        active_workflow.canvas.mask_to_image_map[self._mask_id] = image_id
        return self._mask_id

    def drop_mask_association(
        self,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
    ) -> None:
        """Record stale association removal and mirror real canvas state cleanup."""

        self.dropped_associations.append(association_key)
        mask_id = active_workflow.canvas.mask_associations.pop(association_key, None)
        if mask_id is not None:
            active_workflow.canvas.mask_to_image_map.pop(mask_id, None)

    def update_mask_from_file(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        mask_id: UUID,
        path: Path,
        image_dimensions: tuple[int, int] | None,
        mask_dimensions: tuple[int, int] | None,
    ) -> bool:
        """Record selected-mask pixel updates after service validation."""

        _ = workflow_id, active_workflow, image_id, image_dimensions, mask_dimensions
        self.updated_masks.append((association_key, mask_id, path))
        return True


class _FakeCanvasIoService:
    """Provide deterministic image and mask IO behavior for service tests."""

    def __init__(
        self,
        *,
        image: _FakeImage,
        expected_mask_path: Path,
        allocated_mask_path: Path | None = None,
        dimensions_by_path: dict[Path, tuple[int, int] | None] | None = None,
        created_destinations: list[Path],
    ) -> None:
        self._image = image
        self._expected_mask_path = expected_mask_path
        self._allocated_mask_path = allocated_mask_path or expected_mask_path
        self._dimensions_by_path = dimensions_by_path or {}
        self._created_destinations = created_destinations

    def load_input_image(self, path: Path) -> _FakeImage:
        """Return the configured fake input image."""

        _ = path
        return self._image

    def expected_bound_mask_path(self, **_kwargs: object) -> Path:
        """Return the configured expected bound mask path."""

        return self._expected_mask_path

    def allocate_bound_mask_path(self, **_kwargs: object) -> Path:
        """Return the configured allocated bound mask path."""

        return self._allocated_mask_path

    def image_dimensions(self, path: Path) -> tuple[int, int] | None:
        """Return configured dimensions for an existing mask file."""

        return self._dimensions_by_path.get(path)

    def resolve_mask_path(self, **kwargs: object) -> Path:
        """Resolve a previous buffer path for compatibility checks."""

        path_from_buffer = kwargs["path_from_buffer"]
        assert isinstance(path_from_buffer, str)
        return Path(path_from_buffer)

    def create_blank_mask(self, destination: Path, size: object) -> bool:
        """Persist one blank mask file to the configured destination."""

        _ = size
        self._created_destinations.append(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"blank")
        return True


def _build_workflow(mask_path: str) -> WorkflowState:
    """Build one workflow with a single editable image-mask binding."""

    workflow = WorkflowState()
    workflow.cubes["CubeA"] = CubeState(
        cube_id="CubeA",
        version="1.0.0",
        alias="CubeA",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "input_image": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "E:/images/input.png"},
                },
                "input_mask": {
                    "class_type": "LoadImageMask",
                    "inputs": {"image": mask_path},
                },
                "consumer": {
                    "class_type": "Blend",
                    "inputs": {
                        "image": ["input_image", 0],
                        "mask": ["input_mask", 0],
                    },
                },
            }
        },
    )
    return workflow


def _mask_buffer_path(workflow: WorkflowState) -> str:
    """Return the editable mask image input from a single-cube test workflow."""

    nodes = workflow.cubes["CubeA"].buffer["nodes"]
    assert isinstance(nodes, dict)
    input_mask_node = nodes["input_mask"]
    assert isinstance(input_mask_node, dict)
    input_values = input_mask_node["inputs"]
    assert isinstance(input_values, dict)
    value = input_values["image"]
    assert isinstance(value, str)
    return value


def _image_buffer_path(workflow: WorkflowState) -> str:
    """Return the editable image input from a single-cube test workflow."""

    nodes = workflow.cubes["CubeA"].buffer["nodes"]
    assert isinstance(nodes, dict)
    input_image_node = nodes["input_image"]
    assert isinstance(input_image_node, dict)
    input_values = input_image_node["inputs"]
    assert isinstance(input_values, dict)
    value = input_values["image"]
    assert isinstance(value, str)
    return value


def _mask_asset_payload(workflow: WorkflowState) -> JsonObject:
    """Return the persisted input-mask asset payload from a test workflow."""

    asset_refs = cast(JsonObject, workflow.metadata["asset_refs"])
    input_masks = cast(JsonObject, asset_refs["input_masks"])
    return cast(JsonObject, input_masks["CubeA:input_mask"])


def _workflow_input_service(
    input_canvas_state_service: _FakeInputCanvasStateService,
    canvas_io_service: _FakeCanvasIoService,
) -> WorkflowInputCanvasService:
    """Build the workflow input-canvas service with standard collaborators."""

    return WorkflowInputCanvasService(
        cube_mask_binding_service=CubeMaskBindingService(),
        input_canvas_state_service=input_canvas_state_service,
        canvas_io_service=canvas_io_service,
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
    assert _image_buffer_path(workflow) == "E:\\images\\selected.png"
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
        cube_mask_binding_service=CubeMaskBindingService(),
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


def test_apply_user_selected_input_mask_rejects_wrong_size_before_mutation(
    tmp_path: Path,
) -> None:
    """Wrong-size selected masks should not update pixels or workflow assets."""

    image_id = uuid4()
    mask_id = uuid4()
    workflow = _build_workflow("old-mask.png")
    workflow.canvas.input_key_map["CubeA:input_image"] = image_id
    workflow.canvas.mask_associations[("CubeA", "input_mask")] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = image_id
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
    workflow.canvas.input_key_map["CubeA:input_image"] = image_id
    workflow.canvas.mask_associations[("CubeA", "input_mask")] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = image_id
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
        cube_alias="CubeA",
        node_name="input_mask",
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
        cube_alias="CubeA",
        node_name="input_mask",
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
    assert workflow.canvas.input_key_map["CubeA:input_image"] == image_id
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
    workflow.canvas.mask_associations[("CubeA", "input_mask")] = old_mask_id
    workflow.canvas.mask_to_image_map[old_mask_id] = old_image_id
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
        cube_mask_binding_service=CubeMaskBindingService(),
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
    assert workflow.canvas.mask_associations[("CubeA", "input_mask")] == new_mask_id
    assert workflow.canvas.mask_to_image_map[new_mask_id] == new_image_id
    assert old_mask_id not in workflow.canvas.mask_to_image_map


def test_unambiguous_bound_image_identity_returns_only_bound_input() -> None:
    """Direct canvas loads can target a workflow with one editable image binding."""

    workflow = _build_workflow("")

    identity = _workflow_input_service(
        _FakeInputCanvasStateService(image_id=uuid4(), mask_id=uuid4()),
        _FakeCanvasIoService(
            image=_FakeImage(),
            expected_mask_path=Path("E:/masks/mask.png"),
            created_destinations=[],
        ),
    ).unambiguous_bound_image_identity(workflow)

    assert identity == ("CubeA", "input_image")


def test_resolve_loaded_input_canvas_image_identity_uses_mapped_input_key() -> None:
    """Direct QPane loads should prefer existing workflow input-key ownership."""

    image_id = uuid4()
    workflow = _build_workflow("")
    workflow.canvas.input_key_map["CubeA:input_image"] = image_id
    service = _workflow_input_service(
        _FakeInputCanvasStateService(image_id=uuid4(), mask_id=uuid4()),
        _FakeCanvasIoService(
            image=_FakeImage(),
            expected_mask_path=Path("E:/masks/mask.png"),
            created_destinations=[],
        ),
    )

    resolution = service.resolve_loaded_input_canvas_image_identity(
        workflow,
        image_id,
    )

    assert resolution.accepted is True
    assert resolution.cube_alias == "CubeA"
    assert resolution.image_node_name == "input_image"
    assert resolution.input_key == "CubeA:input_image"


def test_resolve_loaded_input_canvas_image_identity_uses_single_bound_input() -> None:
    """Unmapped direct QPane loads should target one unambiguous graph-bound image."""

    workflow = _build_workflow("")
    image_id = uuid4()
    service = _workflow_input_service(
        _FakeInputCanvasStateService(image_id=uuid4(), mask_id=uuid4()),
        _FakeCanvasIoService(
            image=_FakeImage(),
            expected_mask_path=Path("E:/masks/mask.png"),
            created_destinations=[],
        ),
    )

    resolution = service.resolve_loaded_input_canvas_image_identity(
        workflow,
        image_id,
    )

    assert resolution.accepted is True
    assert resolution.input_key == "CubeA:input_image"
    assert workflow.canvas.input_key_map == {}


def test_resolve_loaded_input_canvas_image_identity_rejects_malformed_key() -> None:
    """Malformed mapped input keys should fail before graph reconciliation."""

    image_id = uuid4()
    workflow = _build_workflow("")
    workflow.canvas.input_key_map["malformed"] = image_id
    service = _workflow_input_service(
        _FakeInputCanvasStateService(image_id=uuid4(), mask_id=uuid4()),
        _FakeCanvasIoService(
            image=_FakeImage(),
            expected_mask_path=Path("E:/masks/mask.png"),
            created_destinations=[],
        ),
    )

    resolution = service.resolve_loaded_input_canvas_image_identity(
        workflow,
        image_id,
    )

    assert resolution.accepted is False
    assert resolution.input_key == "malformed"
    assert resolution.rejection_reason == "malformed_input_key"


def test_resolve_loaded_input_canvas_image_identity_rejects_ambiguous_bound_inputs() -> (
    None
):
    """Direct QPane loads should not guess between multiple graph-bound inputs."""

    workflow = _build_workflow("")
    workflow.cubes["CubeB"] = CubeState(
        cube_id="CubeB",
        version="1.0.0",
        alias="CubeB",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "image": {"class_type": "LoadImage", "inputs": {"image": ""}},
                "mask": {"class_type": "LoadImageMask", "inputs": {"image": ""}},
                "consumer": {
                    "class_type": "Blend",
                    "inputs": {"image": ["image", 0], "mask": ["mask", 0]},
                },
            }
        },
    )
    service = _workflow_input_service(
        _FakeInputCanvasStateService(image_id=uuid4(), mask_id=uuid4()),
        _FakeCanvasIoService(
            image=_FakeImage(),
            expected_mask_path=Path("E:/masks/mask.png"),
            created_destinations=[],
        ),
    )

    resolution = service.resolve_loaded_input_canvas_image_identity(
        workflow,
        uuid4(),
    )

    assert resolution.accepted is False
    assert resolution.rejection_reason == "unmapped_image_id"


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
    ).materialize_loaded_cube(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        cube_alias="CubeA",
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
    ).materialize_loaded_cube(
        workflows={"wf-a": workflow},
        workflow_id="wf-a",
        cube_alias="CubeA",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert results == ()
    assert input_canvas_state_service.loaded_images == []


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
    assert workflow.canvas.input_key_map == {}
    assert input_canvas_state_service.active_input_images == []
