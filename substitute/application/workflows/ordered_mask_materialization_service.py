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

"""Materialize ordered mask endpoints as durable Input canvas region layers."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from substitute.application.workflows.input_canvas_models import (
    MaskMaterializationResult,
)
from substitute.application.workflows.input_canvas_ports import (
    CanvasIoServicePort,
    InputCanvasStateServicePort,
)
from substitute.application.workflows.ordered_mask_graph_value_service import (
    OrderedMaskGraphValueService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import (
    InputCanvasMaskBinding,
    ProjectMaskAssetRef,
    RegionalMaskCollection,
    RegionalMaskEntry,
    WorkflowState,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("application.workflows.ordered_mask_materialization_service")


class OrderedMaskMaterializationService:
    """Own ordered mask-file, graph-list, and canvas-layer materialization."""

    def __init__(
        self,
        *,
        input_canvas_state_service: InputCanvasStateServicePort,
        canvas_io_service: CanvasIoServicePort,
        graph_section_service: WorkflowGraphSectionService,
    ) -> None:
        """Capture focused canvas, filesystem, and graph collaborators."""

        self._input_canvas_state_service = input_canvas_state_service
        self._canvas_io_service = canvas_io_service
        self._graph_section_service = graph_section_service
        self._graph_values = OrderedMaskGraphValueService(graph_section_service)

    def materialize(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        binding: InputCanvasMaskBinding,
        image_id: UUID,
        image: object,
        associated_image_path: Path,
        workflow_name: str,
        projects_dir: Path,
    ) -> tuple[MaskMaterializationResult, ...]:
        """Hydrate every ordered region, creating the initial blank region if empty."""

        image_size = _image_size(image)
        dimensions = _size_dimensions(image_size)
        if image_size is None or dimensions is None:
            log_warning(
                _LOGGER,
                "Ordered mask materialization skipped because image size is unavailable",
                workflow_id=workflow_id,
                section_key=binding.section_key,
                mask_node_name=binding.mask_node_name,
            )
            return ()
        collection = workflow.canvas.ensure_regional_mask_collection(
            binding.association_key
        )
        self._migrate_scalar_entry(
            workflow,
            binding=binding,
            collection=collection,
            image_id=image_id,
        )
        if not collection.entries:
            collection.add_region(image_id)

        results = tuple(
            result
            for entry in tuple(collection.entries)
            if (
                result := self._materialize_entry(
                    workflow=workflow,
                    workflow_id=workflow_id,
                    binding=binding,
                    collection=collection,
                    entry=entry,
                    image_id=image_id,
                    image_size=image_size,
                    dimensions=dimensions,
                    associated_image_path=associated_image_path,
                    workflow_name=workflow_name,
                    projects_dir=projects_dir,
                )
            )
            is not None
        )
        if len(results) != len(collection.entries):
            return results
        self._graph_values.synchronize(workflow, binding, collection)
        log_debug(
            _LOGGER,
            "Materialized ordered regional mask collection",
            workflow_id=workflow_id,
            section_key=binding.section_key,
            mask_node_name=binding.mask_node_name,
            region_count=len(collection.entries),
            image_id=str(image_id),
        )
        return results

    def _migrate_scalar_entry(
        self,
        workflow: WorkflowState,
        *,
        binding: InputCanvasMaskBinding,
        collection: RegionalMaskCollection,
        image_id: UUID,
    ) -> None:
        """Move a legacy one-mask batch association into its ordered collection."""

        if collection.entries:
            return
        legacy_entry = workflow.canvas.mask_entry(binding.association_key)
        if legacy_entry is None or legacy_entry.image_id != image_id:
            return
        workflow.canvas.remove_mask_entry(binding.association_key)
        authored_value = self._graph_section_service.input_value(
            workflow,
            section_key=binding.section_key,
            node_name=binding.mask_node_name,
            field_key=binding.mask_field_key,
        )
        legacy_path = _first_authored_path(authored_value)
        collection.add_region(
            image_id,
            mask_id=legacy_entry.mask_id,
            asset_ref=(
                ProjectMaskAssetRef(legacy_path) if legacy_path is not None else None
            ),
        )
        log_debug(
            _LOGGER,
            "Migrated scalar mask association into ordered regional collection",
            section_key=binding.section_key,
            mask_node_name=binding.mask_node_name,
            mask_id=str(legacy_entry.mask_id),
        )

    def _materialize_entry(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        binding: InputCanvasMaskBinding,
        collection: RegionalMaskCollection,
        entry: RegionalMaskEntry,
        image_id: UUID,
        image_size: object,
        dimensions: tuple[int, int],
        associated_image_path: Path,
        workflow_name: str,
        projects_dir: Path,
    ) -> MaskMaterializationResult | None:
        """Materialize or reuse one ordered region layer and its project asset."""

        if entry.image_id != image_id:
            log_warning(
                _LOGGER,
                "Ordered region belongs to a stale synthetic surface",
                workflow_id=workflow_id,
                section_key=binding.section_key,
                mask_node_name=binding.mask_node_name,
                region_id=str(entry.region_id),
                expected_image_id=str(image_id),
                actual_image_id=str(entry.image_id),
            )
            return None
        resolved_path = self._resolved_entry_path(
            entry,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
        )
        if entry.mask_id is not None:
            if resolved_path is None:
                resolved_path = self._allocate_region_path(
                    binding=binding,
                    entry=entry,
                    associated_image_path=associated_image_path,
                    dimensions=dimensions,
                    workflow_name=workflow_name,
                    projects_dir=projects_dir,
                )
                collection.bind_asset(
                    entry.region_id, ProjectMaskAssetRef(resolved_path.name)
                )
            return MaskMaterializationResult(
                association_key=binding.association_key,
                image_id=image_id,
                mask_id=entry.mask_id,
                resolved_path=resolved_path,
                source="existing_canvas",
            )

        if (
            resolved_path is not None
            and resolved_path.exists()
            and self._canvas_io_service.image_dimensions(resolved_path) == dimensions
        ):
            mask_id = self._load_region_layer(
                workflow=workflow,
                workflow_id=workflow_id,
                binding=binding,
                collection=collection,
                entry=entry,
                image_id=image_id,
                path=resolved_path,
            )
            source = "existing_file"
        else:
            resolved_path = self._allocate_region_path(
                binding=binding,
                entry=entry,
                associated_image_path=associated_image_path,
                dimensions=dimensions,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
            )
            if not self._canvas_io_service.create_blank_mask(
                destination=resolved_path,
                size=image_size,
            ):
                return None
            collection.bind_asset(
                entry.region_id, ProjectMaskAssetRef(resolved_path.name)
            )
            mask_id = self._create_region_layer(
                workflow=workflow,
                workflow_id=workflow_id,
                binding=binding,
                collection=collection,
                entry=entry,
                image_id=image_id,
                image_size=image_size,
            )
            source = "blank_created"
        if mask_id is None:
            return None
        return MaskMaterializationResult(
            association_key=binding.association_key,
            image_id=image_id,
            mask_id=mask_id,
            resolved_path=resolved_path.resolve(),
            source=source,
        )

    def _load_region_layer(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        binding: InputCanvasMaskBinding,
        collection: RegionalMaskCollection,
        entry: RegionalMaskEntry,
        image_id: UUID,
        path: Path,
    ) -> UUID | None:
        """Load one layer through the scalar canvas port, then adopt it regionally."""

        temporary_key = _temporary_association_key(binding, entry)
        mask_id = self._input_canvas_state_service.load_mask_from_file(
            workflow_id,
            workflow,
            temporary_key,
            image_id,
            path,
        )
        adopted_mask_id = _adopt_temporary_layer(
            workflow,
            collection=collection,
            entry=entry,
            temporary_key=temporary_key,
            mask_id=mask_id,
        )
        if adopted_mask_id is not None:
            self._input_canvas_state_service.apply_materialized_mask_visual_opacity(
                workflow_id,
                workflow,
                binding.association_key,
                adopted_mask_id,
            )
        return adopted_mask_id

    def _create_region_layer(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        binding: InputCanvasMaskBinding,
        collection: RegionalMaskCollection,
        entry: RegionalMaskEntry,
        image_id: UUID,
        image_size: object,
    ) -> UUID | None:
        """Create one blank layer through the scalar port, then adopt it regionally."""

        temporary_key = _temporary_association_key(binding, entry)
        mask_id = self._input_canvas_state_service.create_mask_for_image(
            workflow_id,
            workflow,
            temporary_key,
            image_id,
            image_size,
        )
        adopted_mask_id = _adopt_temporary_layer(
            workflow,
            collection=collection,
            entry=entry,
            temporary_key=temporary_key,
            mask_id=mask_id,
        )
        if adopted_mask_id is not None:
            self._input_canvas_state_service.apply_materialized_mask_visual_opacity(
                workflow_id,
                workflow,
                binding.association_key,
                adopted_mask_id,
            )
        return adopted_mask_id

    def _allocate_region_path(
        self,
        *,
        binding: InputCanvasMaskBinding,
        entry: RegionalMaskEntry,
        associated_image_path: Path,
        dimensions: tuple[int, int],
        workflow_name: str,
        projects_dir: Path,
    ) -> Path:
        """Allocate a stable project-mask path unique to one region identity."""

        return self._canvas_io_service.expected_bound_mask_path(
            workflow_name=workflow_name,
            associated_image_path=associated_image_path,
            cube_alias=binding.section_key,
            mask_node_name=f"{binding.mask_node_name}-{entry.region_id.hex}",
            image_size=dimensions,
            projects_dir=projects_dir,
        )

    def _resolved_entry_path(
        self,
        entry: RegionalMaskEntry,
        *,
        workflow_name: str,
        projects_dir: Path,
    ) -> Path | None:
        """Resolve one project mask reference through the canvas path boundary."""

        asset_ref = entry.asset_ref
        if not isinstance(asset_ref, ProjectMaskAssetRef):
            return None
        try:
            return self._canvas_io_service.resolve_mask_path(
                workflow_name=workflow_name,
                path_from_buffer=asset_ref.relative_path,
                projects_dir=projects_dir,
            )
        except ValueError:
            return None


def _temporary_association_key(
    binding: InputCanvasMaskBinding,
    entry: RegionalMaskEntry,
) -> tuple[str, str]:
    """Return an internal scalar-port key that cannot collide with authored nodes."""

    return (
        binding.section_key,
        f"@regional/{binding.mask_node_name}/{entry.region_id.hex}",
    )


def _adopt_temporary_layer(
    workflow: WorkflowState,
    *,
    collection: RegionalMaskCollection,
    entry: RegionalMaskEntry,
    temporary_key: tuple[str, str],
    mask_id: UUID | None,
) -> UUID | None:
    """Transfer a newly created scalar-port layer into its ordered collection."""

    if mask_id is None:
        return None
    temporary_entry = workflow.canvas.remove_mask_entry(temporary_key)
    if temporary_entry is None or temporary_entry.mask_id != mask_id:
        raise RuntimeError("Canvas mask port did not bind its returned layer identity.")
    collection.bind_mask_layer(entry.region_id, mask_id)
    return mask_id


def _image_size(image: object) -> object | None:
    """Return a Qt-like image size payload when available."""

    getter = getattr(image, "size", None)
    return getter() if callable(getter) else None


def _first_authored_path(value: object) -> str | None:
    """Return the first persisted mask path from scalar or ordered graph input."""

    if isinstance(value, str) and value:
        return value
    if isinstance(value, list):
        return next((item for item in value if isinstance(item, str) and item), None)
    return None


def _size_dimensions(size: object | None) -> tuple[int, int] | None:
    """Return validated dimensions from a Qt-like size payload."""

    if size is None:
        return None
    width_getter = getattr(size, "width", None)
    height_getter = getattr(size, "height", None)
    if not callable(width_getter) or not callable(height_getter):
        return None
    try:
        width = int(width_getter())
        height = int(height_getter())
    except (TypeError, ValueError):
        return None
    return (width, height) if width > 0 and height > 0 else None


__all__ = ["OrderedMaskMaterializationService"]
