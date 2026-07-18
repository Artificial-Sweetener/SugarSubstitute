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

"""Own editable mask path selection and canvas layer materialization."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from substitute.application.workflows.input_canvas_ports import (
    CanvasIoServicePort,
    InputCanvasStateServicePort,
    WorkflowAssetServicePort,
)
from substitute.application.workflows.input_canvas_models import (
    MaskMaterializationResult,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import InputCanvasMaskBinding, WorkflowState
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("application.workflows.input_mask_materialization_service")


class InputMaskMaterializationService:
    """Own editable-mask filesystem and canvas-layer materialization."""

    def __init__(
        self,
        *,
        input_canvas_state_service: InputCanvasStateServicePort,
        canvas_io_service: CanvasIoServicePort,
        workflow_asset_service: WorkflowAssetServicePort,
        graph_section_service: WorkflowGraphSectionService,
    ) -> None:
        """Capture the focused state, IO, asset, and graph collaborators."""

        self._input_canvas_state_service = input_canvas_state_service
        self._canvas_io_service = canvas_io_service
        self._workflow_asset_service = workflow_asset_service
        self._graph_section_service = graph_section_service

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
    ) -> MaskMaterializationResult | None:
        """Hydrate or create one mask layer for a discovered editable binding."""

        resolved_size = self._image_size(image)
        if resolved_size is None:
            log_warning(
                _LOGGER,
                "Editable mask materialization skipped because image size is unavailable",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                section_key=binding.section_key,
                canvas_surface_key=binding.surface_key,
                mask_node_name=binding.mask_node_name,
                input_image_path=str(associated_image_path),
            )
            return None
        image_dimensions = self._size_dimensions(resolved_size)
        if image_dimensions is None:
            log_warning(
                _LOGGER,
                "Editable mask materialization skipped because image dimensions are invalid",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                section_key=binding.section_key,
                canvas_surface_key=binding.surface_key,
                mask_node_name=binding.mask_node_name,
                input_image_path=str(associated_image_path),
                size_type=type(resolved_size).__name__,
            )
            return None

        raw_mask_path = self._graph_section_service.input_value(
            workflow,
            section_key=binding.section_key,
            node_name=binding.mask_node_name,
            field_key=binding.mask_field_key,
        )
        old_mask_path = raw_mask_path if isinstance(raw_mask_path, str) else ""
        explicit_mask_path = self._explicit_mask_asset_path(
            workflow=workflow,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            binding=binding,
            projects_dir=projects_dir,
        )
        expected_mask_path = self._canvas_io_service.expected_bound_mask_path(
            workflow_name=workflow_name,
            associated_image_path=associated_image_path,
            cube_alias=binding.section_key,
            mask_node_name=binding.mask_node_name,
            image_size=image_dimensions,
            projects_dir=projects_dir,
        )
        selected_mask_path = expected_mask_path
        resolved_expected_text = str(expected_mask_path.resolve())
        if old_mask_path and old_mask_path != resolved_expected_text:
            log_debug(
                _LOGGER,
                "Editable mask buffer path differs from input-bound expected path",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                section_key=binding.section_key,
                canvas_surface_key=binding.surface_key,
                mask_node_name=binding.mask_node_name,
                input_image_path=str(associated_image_path),
                old_mask_path=old_mask_path,
                expected_mask_path=resolved_expected_text,
            )

        existing_canvas_mask = self._existing_canvas_mask_result(
            workflow=workflow,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            binding=binding,
            image_id=image_id,
            resolved_path=explicit_mask_path or expected_mask_path,
        )
        if existing_canvas_mask is not None:
            return existing_canvas_mask

        if explicit_mask_path is not None and explicit_mask_path.exists():
            explicit_mask_dimensions = self._canvas_io_service.image_dimensions(
                explicit_mask_path
            )
            if explicit_mask_dimensions == image_dimensions:
                log_debug(
                    _LOGGER,
                    "Hydrating explicit editable mask asset",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    section_key=binding.section_key,
                    canvas_surface_key=binding.surface_key,
                    mask_node_name=binding.mask_node_name,
                    input_image_path=str(associated_image_path),
                    selected_mask_path=str(explicit_mask_path.resolve()),
                    expected_size=image_dimensions,
                    actual_mask_size=explicit_mask_dimensions,
                )
                mask_id = self._input_canvas_state_service.load_mask_from_file(
                    workflow_id,
                    workflow,
                    binding.association_key,
                    image_id,
                    explicit_mask_path,
                )
                if mask_id is None:
                    return None
                return MaskMaterializationResult(
                    association_key=binding.association_key,
                    image_id=image_id,
                    mask_id=mask_id,
                    resolved_path=explicit_mask_path,
                    source="manual_file",
                )
            log_warning(
                _LOGGER,
                "Explicit editable mask asset dimensions mismatch input image",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                section_key=binding.section_key,
                canvas_surface_key=binding.surface_key,
                mask_node_name=binding.mask_node_name,
                input_image_path=str(associated_image_path),
                selected_mask_path=str(explicit_mask_path.resolve()),
                expected_size=image_dimensions,
                actual_mask_size=explicit_mask_dimensions,
            )

        if expected_mask_path.exists():
            mask_dimensions = self._canvas_io_service.image_dimensions(
                expected_mask_path
            )
            if mask_dimensions == image_dimensions:
                self._associate_project_mask(
                    workflow=workflow,
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    binding=binding,
                    path=expected_mask_path,
                )
                log_debug(
                    _LOGGER,
                    "Hydrating input-bound editable mask",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    section_key=binding.section_key,
                    canvas_surface_key=binding.surface_key,
                    mask_node_name=binding.mask_node_name,
                    input_image_path=str(associated_image_path),
                    selected_mask_path=resolved_expected_text,
                    expected_size=image_dimensions,
                    actual_mask_size=mask_dimensions,
                )
                mask_id = self._input_canvas_state_service.load_mask_from_file(
                    workflow_id,
                    workflow,
                    binding.association_key,
                    image_id,
                    expected_mask_path,
                )
                if mask_id is None:
                    return None
                return MaskMaterializationResult(
                    association_key=binding.association_key,
                    image_id=image_id,
                    mask_id=mask_id,
                    resolved_path=expected_mask_path,
                    source="existing_file",
                )
            compatible_previous_path = self._compatible_previous_mask_path(
                raw_mask_path=old_mask_path,
                expected_mask_path=expected_mask_path,
                image_dimensions=image_dimensions,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
            )
            if compatible_previous_path is not None:
                self._associate_project_mask(
                    workflow=workflow,
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    binding=binding,
                    path=compatible_previous_path,
                )
                log_debug(
                    _LOGGER,
                    "Hydrating compatible previous editable mask variant",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    section_key=binding.section_key,
                    canvas_surface_key=binding.surface_key,
                    mask_node_name=binding.mask_node_name,
                    input_image_path=str(associated_image_path),
                    expected_mask_path=resolved_expected_text,
                    selected_mask_path=str(compatible_previous_path.resolve()),
                    expected_size=image_dimensions,
                )
                mask_id = self._input_canvas_state_service.load_mask_from_file(
                    workflow_id,
                    workflow,
                    binding.association_key,
                    image_id,
                    compatible_previous_path,
                )
                if mask_id is None:
                    return None
                return MaskMaterializationResult(
                    association_key=binding.association_key,
                    image_id=image_id,
                    mask_id=mask_id,
                    resolved_path=compatible_previous_path,
                    source="existing_file",
                )
            if mask_dimensions is None:
                log_warning(
                    _LOGGER,
                    "Expected editable mask dimensions are unavailable",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    section_key=binding.section_key,
                    canvas_surface_key=binding.surface_key,
                    mask_node_name=binding.mask_node_name,
                    input_image_path=str(associated_image_path),
                    expected_mask_path=resolved_expected_text,
                    expected_size=image_dimensions,
                )
            else:
                log_warning(
                    _LOGGER,
                    "Expected editable mask dimensions mismatch input image",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    section_key=binding.section_key,
                    canvas_surface_key=binding.surface_key,
                    mask_node_name=binding.mask_node_name,
                    input_image_path=str(associated_image_path),
                    expected_mask_path=resolved_expected_text,
                    expected_size=image_dimensions,
                    actual_mask_size=mask_dimensions,
                )
            selected_mask_path = self._canvas_io_service.allocate_bound_mask_path(
                workflow_name=workflow_name,
                associated_image_path=associated_image_path,
                cube_alias=binding.section_key,
                mask_node_name=binding.mask_node_name,
                image_size=image_dimensions,
                projects_dir=projects_dir,
            )
            log_debug(
                _LOGGER,
                "Creating compatible replacement editable mask",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                section_key=binding.section_key,
                canvas_surface_key=binding.surface_key,
                mask_node_name=binding.mask_node_name,
                input_image_path=str(associated_image_path),
                old_mask_path=old_mask_path,
                expected_mask_path=resolved_expected_text,
                selected_mask_path=str(selected_mask_path.resolve()),
                expected_size=image_dimensions,
                actual_mask_size=mask_dimensions,
            )
        else:
            log_debug(
                _LOGGER,
                "Creating missing input-bound editable mask",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                section_key=binding.section_key,
                canvas_surface_key=binding.surface_key,
                mask_node_name=binding.mask_node_name,
                input_image_path=str(associated_image_path),
                selected_mask_path=resolved_expected_text,
                expected_size=image_dimensions,
            )
            compatible_previous_path = self._compatible_previous_mask_path(
                raw_mask_path=old_mask_path,
                expected_mask_path=expected_mask_path,
                image_dimensions=image_dimensions,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
            )
            if compatible_previous_path is not None:
                self._associate_project_mask(
                    workflow=workflow,
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    binding=binding,
                    path=compatible_previous_path,
                )
                log_debug(
                    _LOGGER,
                    "Hydrating compatible previous editable mask variant",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    section_key=binding.section_key,
                    canvas_surface_key=binding.surface_key,
                    mask_node_name=binding.mask_node_name,
                    input_image_path=str(associated_image_path),
                    expected_mask_path=resolved_expected_text,
                    selected_mask_path=str(compatible_previous_path.resolve()),
                    expected_size=image_dimensions,
                )
                mask_id = self._input_canvas_state_service.load_mask_from_file(
                    workflow_id,
                    workflow,
                    binding.association_key,
                    image_id,
                    compatible_previous_path,
                )
                if mask_id is None:
                    return None
                return MaskMaterializationResult(
                    association_key=binding.association_key,
                    image_id=image_id,
                    mask_id=mask_id,
                    resolved_path=compatible_previous_path,
                    source="existing_file",
                )

        if not self._canvas_io_service.create_blank_mask(
            destination=selected_mask_path,
            size=resolved_size,
        ):
            log_warning(
                _LOGGER,
                "Editable mask materialization failed because blank mask file could not be created",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                section_key=binding.section_key,
                canvas_surface_key=binding.surface_key,
                mask_node_name=binding.mask_node_name,
                input_image_path=str(associated_image_path),
                selected_mask_path=str(selected_mask_path),
                expected_size=image_dimensions,
            )
            return None

        self._associate_project_mask(
            workflow=workflow,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            binding=binding,
            path=selected_mask_path,
        )
        mask_id = self._input_canvas_state_service.create_mask_for_image(
            workflow_id,
            workflow,
            binding.association_key,
            image_id,
            resolved_size,
        )
        if mask_id is None:
            log_warning(
                _LOGGER,
                "Editable mask materialization failed because input canvas returned no mask id",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                section_key=binding.section_key,
                canvas_surface_key=binding.surface_key,
                mask_node_name=binding.mask_node_name,
                image_id=str(image_id),
                input_image_path=str(associated_image_path),
                selected_mask_path=str(selected_mask_path),
                expected_size=image_dimensions,
            )
            return None
        return MaskMaterializationResult(
            association_key=binding.association_key,
            image_id=image_id,
            mask_id=mask_id,
            resolved_path=selected_mask_path.resolve(),
            source="blank_created",
        )

    def _existing_canvas_mask_result(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        workflow_name: str,
        binding: InputCanvasMaskBinding,
        image_id: UUID,
        resolved_path: Path,
    ) -> MaskMaterializationResult | None:
        """Reuse the live canvas mask for a binding when it already targets image_id."""

        mask_id = workflow.canvas.mask_associations.get(binding.association_key)
        if mask_id is None:
            return None

        associated_image_id = workflow.canvas.mask_to_image_map.get(mask_id)
        if associated_image_id == image_id:
            log_debug(
                _LOGGER,
                "Reusing live editable mask layer for input image binding",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                section_key=binding.section_key,
                canvas_surface_key=binding.surface_key,
                mask_node_name=binding.mask_node_name,
                image_id=str(image_id),
                mask_id=str(mask_id),
                resolved_path=str(resolved_path),
            )
            return MaskMaterializationResult(
                association_key=binding.association_key,
                image_id=image_id,
                mask_id=mask_id,
                resolved_path=resolved_path,
                source="existing_canvas",
            )

        log_warning(
            _LOGGER,
            "Dropping stale editable mask association before rematerialization",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            section_key=binding.section_key,
            canvas_surface_key=binding.surface_key,
            mask_node_name=binding.mask_node_name,
            image_id=str(image_id),
            mask_id=str(mask_id),
            associated_image_id=(
                str(associated_image_id) if associated_image_id is not None else ""
            ),
        )
        self._input_canvas_state_service.drop_mask_association(
            workflow,
            binding.association_key,
        )
        return None

    def _associate_project_mask(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        workflow_name: str,
        binding: InputCanvasMaskBinding,
        path: Path,
    ) -> None:
        """Store project-mask ownership for one materialized editable mask."""

        relative_path = path.name
        associated = self._workflow_asset_service.associate_project_input_mask(
            workflow,
            section_key=binding.section_key,
            node_name=binding.mask_node_name,
            field_key=binding.mask_field_key,
            relative_path=relative_path,
        )
        log_debug(
            _LOGGER,
            "Associated materialized editable mask with workflow asset state",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            section_key=binding.section_key,
            canvas_surface_key=binding.surface_key,
            mask_node_name=binding.mask_node_name,
            mask_path=str(path.resolve()),
            relative_path=relative_path,
            association_succeeded=associated,
        )

    @staticmethod
    def _image_size(image: object) -> object | None:
        """Return image size payload when the image exposes one."""

        size = getattr(image, "size", None)
        if callable(size):
            resolved_size: object = size()
            return resolved_size
        return None

    @staticmethod
    def _size_dimensions(size: object) -> tuple[int, int] | None:
        """Return concrete width and height from a Qt-like size object."""

        width_getter = getattr(size, "width", None)
        height_getter = getattr(size, "height", None)
        if not callable(width_getter) or not callable(height_getter):
            return None
        try:
            width = int(width_getter())
            height = int(height_getter())
        except (TypeError, ValueError):
            return None
        if width <= 0 or height <= 0:
            return None
        return (width, height)

    def _compatible_previous_mask_path(
        self,
        *,
        raw_mask_path: str,
        expected_mask_path: Path,
        image_dimensions: tuple[int, int],
        workflow_name: str,
        projects_dir: Path,
    ) -> Path | None:
        """Return a prior compatible variant for the current expected mask path."""

        if not raw_mask_path:
            return None
        try:
            candidate = self._canvas_io_service.resolve_mask_path(
                workflow_name=workflow_name,
                path_from_buffer=raw_mask_path,
                projects_dir=projects_dir,
            )
        except ValueError:
            return None
        if not candidate.exists():
            return None
        if not self._is_current_bound_variant(
            candidate_path=candidate,
            expected_mask_path=expected_mask_path,
        ):
            return None
        if self._canvas_io_service.image_dimensions(candidate) != image_dimensions:
            return None
        return candidate

    @staticmethod
    def _is_current_bound_variant(
        *,
        candidate_path: Path,
        expected_mask_path: Path,
    ) -> bool:
        """Return whether candidate is the expected path or its versioned variant."""

        if candidate_path.resolve().parent != expected_mask_path.resolve().parent:
            return False
        if candidate_path.suffix.casefold() != expected_mask_path.suffix.casefold():
            return False
        if candidate_path.stem == expected_mask_path.stem:
            return True
        return candidate_path.stem.startswith(f"{expected_mask_path.stem}__v")

    def _explicit_mask_asset_path(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        workflow_name: str,
        binding: InputCanvasMaskBinding,
        projects_dir: Path,
    ) -> Path | None:
        """Return a durable mask asset path when the mask node has metadata."""

        asset_ref = self._workflow_asset_service.input_mask_asset_ref(
            workflow,
            section_key=binding.section_key,
            node_name=binding.mask_node_name,
            field_key=binding.mask_field_key,
        )
        if asset_ref is None:
            return None
        resolved_path = self._workflow_asset_service.resolve_input_mask_path(
            workflow,
            workflow_name=workflow_name,
            section_key=binding.section_key,
            node_name=binding.mask_node_name,
            field_key=binding.mask_field_key,
            projects_dir=projects_dir,
        )
        log_debug(
            _LOGGER,
            "Resolved explicit editable mask asset path",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            section_key=binding.section_key,
            canvas_surface_key=binding.surface_key,
            mask_node_name=binding.mask_node_name,
            asset_ref_kind=getattr(asset_ref, "kind", ""),
            resolved_path=str(resolved_path) if resolved_path is not None else "",
        )
        return resolved_path


__all__ = ["InputMaskMaterializationService"]
