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

"""Provide workflow Input-canvas collaborator doubles."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from uuid import UUID
from substitute.domain.common import JsonObject
from substitute.domain.workflow import WorkflowState


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


class _DefinitionGateway:
    """Return deterministic live node definitions for planner integration tests."""

    def __init__(self, definitions: Mapping[str, JsonObject]) -> None:
        self._definitions = definitions

    def get_node_definition(self, node_class: str) -> JsonObject:
        """Return one cached definition."""

        return self._definitions.get(node_class, {})

    def get_required_node_definition(self, node_class: str) -> JsonObject:
        """Return one required definition through the same deterministic cache."""

        return self.get_node_definition(node_class)


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
        self.removed_masks: list[tuple[UUID, UUID]] = []
        self.input_path = Path("synthetic.png")
        self.activated_masks: list[UUID] = []

    def input_image_path(self, image_id: UUID) -> Path | None:
        """Return a deterministic path for an owned fake image."""

        return self.input_path if image_id == self._image_id else None

    def set_active_workflow_mask(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        mask_id: UUID,
    ) -> bool:
        """Record ordered-region activation."""

        _ = workflow_id
        workflow.canvas.active_input_mask_uuid = mask_id
        self.activated_masks.append(mask_id)
        return True

    def apply_materialized_mask_visual_opacity(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        association_key: tuple[str, str],
        mask_id: UUID,
    ) -> bool:
        """Accept node-level presentation projection in materialization tests."""

        _ = workflow_id, workflow, association_key, mask_id
        return True

    def set_mask_visual_opacity(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        association_key: tuple[str, str],
        opacity: float,
    ) -> bool:
        """Accept node-level presentation changes in graph-service tests."""

        _ = workflow_id, workflow, association_key, opacity
        return True

    def mask_ids_for_association(
        self,
        workflow: WorkflowState,
        association_key: tuple[str, str],
    ) -> tuple[UUID, ...]:
        """Return the configured fake mask for protocol completeness."""

        _ = workflow, association_key
        return (self._mask_id,)

    def synchronize_mask_visual_opacity_state(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        association_key: tuple[str, str],
        opacity: float,
    ) -> bool:
        """Accept restored document state for protocol completeness."""

        _ = workflow_id, workflow, association_key, opacity
        return True

    def load_input_image(
        self,
        workflows: object,
        active_workflow_id: str,
        input_key: str,
        image: object,
        path: Path,
    ) -> UUID:
        """Return the configured input image identifier."""

        _ = image
        self.loaded_images.append((input_key, path))
        if isinstance(workflows, Mapping):
            workflow = workflows.get(active_workflow_id)
            if isinstance(workflow, WorkflowState):
                workflow.canvas.bind_image(input_key, self._image_id)
                workflow.canvas.input_image_uuid = self._image_id
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
        workflow.canvas.replace_image_entry(input_key, image_id)
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
        active_workflow.canvas.replace_mask_entry(
            association_key,
            self._mask_id,
            image_id,
        )
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
        active_workflow.canvas.replace_mask_entry(
            association_key,
            self._mask_id,
            image_id,
        )
        return self._mask_id

    def drop_mask_association(
        self,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
    ) -> None:
        """Record stale association removal and mirror real canvas state cleanup."""

        self.dropped_associations.append(association_key)
        active_workflow.canvas.remove_mask_entry(association_key)

    def drop_input_surface(
        self,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        input_key: str,
    ) -> bool:
        """Drop one fake surface and all masks associated with its image."""

        workflow = workflows.get(workflow_id)
        if workflow is None:
            return False
        image_entry = workflow.canvas.remove_image_entry(input_key)
        if image_entry is None:
            return False
        for association_key, mask_entry in tuple(workflow.canvas.mask_entries.items()):
            if mask_entry.image_id != image_entry.image_id:
                continue
            self.drop_mask_association(workflow, association_key)
        return True

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

    def remove_workflow_mask_layer(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        image_id: UUID,
        mask_id: UUID,
    ) -> bool:
        """Record removal of one exact ordered mask layer."""

        _ = workflow_id, active_workflow
        self.removed_masks.append((image_id, mask_id))
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

    def create_blank_input_surface(
        self,
        *,
        destination: Path,
        width: int,
        height: int,
    ) -> _FakeImage:
        """Return the configured image for a synthetic backing request."""

        _ = destination, width, height
        return self._image

    def synthetic_input_surface_path(self, **_kwargs: object) -> Path:
        """Return a deterministic fake synthetic backing path."""

        return self._expected_mask_path.with_name("synthetic.png")

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
        path = Path(path_from_buffer)
        if path.is_absolute():
            return path
        projects_dir = kwargs["projects_dir"]
        workflow_name = kwargs["workflow_name"]
        assert isinstance(projects_dir, Path)
        assert isinstance(workflow_name, str)
        return projects_dir / workflow_name / "masks" / path

    def create_blank_mask(self, destination: Path, size: object) -> bool:
        """Persist one blank mask file to the configured destination."""

        _ = size
        self._created_destinations.append(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"blank")
        return True

    def save_resampled_mask(
        self,
        source: Path,
        destination: Path,
        *,
        width: int,
        height: int,
    ) -> bool:
        """Record an imported mask normalized to exact target dimensions."""

        if not source.is_file() or width <= 0 or height <= 0:
            return False
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"resampled")
        self._dimensions_by_path[destination] = (width, height)
        return True
