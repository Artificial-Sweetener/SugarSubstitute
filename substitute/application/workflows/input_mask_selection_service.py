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

"""Validate and apply user-selected scalar Input masks."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from time import perf_counter

from substitute.application.workflows.input_canvas_binding_service import (
    InputCanvasBindingService,
)
from substitute.application.workflows.input_canvas_models import (
    InputCanvasMaterializationResult,
    UserSelectedInputMaskResult,
)
from substitute.application.workflows.input_canvas_ports import (
    CanvasIoServicePort,
    WorkflowAssetServicePort,
)
from substitute.application.workflows.input_image_asset_service import (
    InputImageAssetService,
)
from substitute.application.workflows.input_mask_asset_service import (
    InputMaskAssetService,
)
from substitute.application.workflows.input_mask_binding_materialization_service import (
    InputMaskBindingMaterializationService,
)
from substitute.application.workflows.synthetic_input_canvas_surface_service import (
    SyntheticInputCanvasSurfaceService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import InputCanvasSurface, InputCanvasSurfaceKind
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("application.workflows.input_mask_selection_service")


class InputMaskSelectionService:
    """Own the atomic validation, canvas update, and graph association transaction."""

    def __init__(
        self,
        *,
        bindings: InputCanvasBindingService,
        images: InputImageAssetService,
        masks: InputMaskAssetService,
        canvas_io: CanvasIoServicePort,
        workflow_assets: WorkflowAssetServicePort,
        graph_sections: WorkflowGraphSectionService,
        synthetic_surfaces: SyntheticInputCanvasSurfaceService,
        mask_materialization: InputMaskBindingMaterializationService,
    ) -> None:
        """Store graph, live-canvas, persistence, and materialization owners."""

        self._bindings = bindings
        self._images = images
        self._masks = masks
        self._canvas_io = canvas_io
        self._workflow_assets = workflow_assets
        self._graph_sections = graph_sections
        self._synthetic_surfaces = synthetic_surfaces
        self._mask_materialization = mask_materialization

    def apply_user_selected_input_mask(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        cube_alias: str,
        mask_node_name: str,
        mask_path: str,
        workflow_name: str,
        projects_dir: Path,
    ) -> UserSelectedInputMaskResult:
        """Validate and apply one user-selected mask through Input ownership."""

        workflow = workflows.get(workflow_id)
        if workflow is None or not mask_path:
            return UserSelectedInputMaskResult.rejected(
                "missing_workflow_or_mask_path",
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
            )

        binding = self._bindings.binding_for_mask(workflow, cube_alias, mask_node_name)
        if binding is None:
            log_warning(
                _LOGGER,
                "Rejected user-selected input mask without graph binding",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
                rejection_reason="missing_mask_binding",
            )
            return UserSelectedInputMaskResult.rejected(
                "missing_mask_binding",
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
            )

        image_entry = workflow.canvas.image_entry(binding.surface.input_key)
        image_id = image_entry.image_id if image_entry is not None else None
        image_path = self._surface_image_path(
            workflow,
            binding.surface,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
        )
        if image_id is None or not image_path:
            log_warning(
                _LOGGER,
                "Rejected user-selected input mask without materialized image binding",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
                input_key=binding.surface.input_key,
                rejection_reason="missing_bound_input_image",
            )
            return UserSelectedInputMaskResult.rejected(
                "missing_bound_input_image",
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
            )

        image_dimensions = self._canvas_io.image_dimensions(Path(image_path))
        mask_dimensions = self._canvas_io.image_dimensions(Path(mask_path))
        if image_dimensions is None or mask_dimensions is None:
            return UserSelectedInputMaskResult.rejected(
                "unverified_dimensions",
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
                selected_dimensions=mask_dimensions,
                required_dimensions=image_dimensions,
            )
        if image_dimensions != mask_dimensions:
            return UserSelectedInputMaskResult.rejected(
                "dimension_mismatch",
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
                selected_dimensions=mask_dimensions,
                required_dimensions=image_dimensions,
            )

        association_key = binding.association_key
        materialization_result: InputCanvasMaterializationResult | None = None
        mask_entry = workflow.canvas.mask_entry(association_key)
        mask_id = mask_entry.mask_id if mask_entry is not None else None
        if mask_id is None:
            image = self._canvas_io.load_input_image(Path(image_path))
            if image is not None:
                self._images.claim_loaded(
                    workflow_id,
                    workflow,
                    binding.surface.input_key,
                    image_id,
                )
                materialization_result = self._mask_materialization.materialize(
                    workflow=workflow,
                    workflow_id=workflow_id,
                    section_key=binding.section_key,
                    surface_key=binding.surface_key,
                    bindings=self._bindings.bindings_for_image(
                        workflow,
                        binding.section_key,
                        binding.surface_key,
                    ),
                    image_id=image_id,
                    image=image,
                    associated_image_path=Path(image_path),
                    workflow_name=workflow_name,
                    projects_dir=projects_dir,
                    started_at=perf_counter(),
                )
            mask_entry = workflow.canvas.mask_entry(association_key)
            mask_id = mask_entry.mask_id if mask_entry is not None else None
        if mask_id is None:
            log_warning(
                _LOGGER,
                "Rejected user-selected input mask because no canvas mask is associated",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
                image_id=str(image_id),
                rejection_reason="missing_canvas_mask",
            )
            return UserSelectedInputMaskResult.rejected(
                "missing_canvas_mask",
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
            )

        updated = self._masks.update_from_file(
            workflow_id,
            workflow,
            association_key,
            image_id,
            mask_id,
            Path(mask_path),
            image_dimensions,
            mask_dimensions,
        )
        if not updated:
            log_warning(
                _LOGGER,
                "Rejected user-selected input mask because canvas pixels were not updated",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
                mask_id=str(mask_id),
                image_id=str(image_id),
                rejection_reason="mask_pixel_update_failed",
            )
            return UserSelectedInputMaskResult.rejected(
                "mask_pixel_update_failed",
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
            )

        associated = self._workflow_assets.associate_local_input_mask(
            workflow,
            section_key=binding.section_key,
            node_name=mask_node_name,
            field_key=binding.mask_field_key,
            mask_path=mask_path,
        )
        log_debug(
            _LOGGER,
            "Applied user-selected input mask",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            node_name=mask_node_name,
            mask_path=mask_path,
            mask_id=str(mask_id),
            association_succeeded=associated,
            mask_pixels_updated=updated,
            image_id=str(image_id),
        )
        return UserSelectedInputMaskResult.accepted(
            cube_alias=cube_alias,
            node_name=mask_node_name,
            mask_path=mask_path,
            materialization_result=materialization_result,
        )

    def _surface_image_path(
        self,
        workflow: WorkflowState,
        surface: InputCanvasSurface,
        *,
        workflow_name: str,
        projects_dir: Path,
    ) -> str:
        """Return the authored or deterministic synthetic backing image path."""

        endpoint = surface.image_endpoint
        if endpoint is not None:
            value = self._graph_sections.input_value(
                workflow,
                section_key=endpoint.section_key,
                node_name=endpoint.node_name,
                field_key=endpoint.field_key,
            )
            return value if isinstance(value, str) else ""
        dimensions = surface.dimensions
        if surface.kind is not InputCanvasSurfaceKind.SYNTHETIC or dimensions is None:
            return ""
        return str(
            self._synthetic_surfaces.path_for_surface(
                surface,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
            )
        )


__all__ = ["InputMaskSelectionService"]
