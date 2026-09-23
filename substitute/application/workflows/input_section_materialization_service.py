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

"""Materialize every input-canvas surface owned by one graph section."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Mapping

from substitute.application.workflows.input_canvas_binding_service import (
    InputCanvasBindingService,
)
from substitute.application.workflows.input_canvas_models import (
    InputCanvasMaterializationResult,
)
from substitute.application.workflows.input_image_materialization_service import (
    InputImageMaterializationService,
    looks_like_local_path,
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
from substitute.shared.logging.logger import get_logger, log_info, log_timing

_LOGGER = get_logger("application.workflows.input_section_materialization_service")


class InputSectionMaterializationService:
    """Own restoration of authored and synthetic surfaces for graph sections."""

    def __init__(
        self,
        *,
        bindings: InputCanvasBindingService,
        images: InputImageMaterializationService,
        mask_materialization: InputMaskBindingMaterializationService,
        synthetic_surfaces: SyntheticInputCanvasSurfaceService,
        graph_sections: WorkflowGraphSectionService,
    ) -> None:
        """Store the focused owners needed to restore section surfaces."""

        self._bindings = bindings
        self._images = images
        self._mask_materialization = mask_materialization
        self._synthetic_surfaces = synthetic_surfaces
        self._graph_sections = graph_sections

    def materialize_loaded_section(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        section_key: str,
        workflow_name: str,
        projects_dir: Path,
    ) -> tuple[InputCanvasMaterializationResult, ...]:
        """Materialize authored and synthetic surfaces from one graph section."""

        started_at = perf_counter()
        workflow = workflows.get(workflow_id)
        if workflow is None:
            return ()
        plan = self._bindings.plan(workflow, section_key)
        self._synthetic_surfaces.invalidate_stale(
            workflows=workflows,
            workflow_id=workflow_id,
            workflow=workflow,
            section_key=section_key,
            plan=plan,
        )
        synthetic_surfaces = tuple(
            surface
            for surface in plan.surfaces
            if surface.kind is InputCanvasSurfaceKind.SYNTHETIC
        )
        results = self._materialize_authored_images(
            workflows=workflows,
            workflow=workflow,
            workflow_id=workflow_id,
            section_key=section_key,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
        )
        results.extend(
            result
            for surface in synthetic_surfaces
            if (
                result := self._materialize_synthetic_surface(
                    workflows=workflows,
                    workflow=workflow,
                    workflow_id=workflow_id,
                    surface=surface,
                    workflow_name=workflow_name,
                    projects_dir=projects_dir,
                )
            ).image_id
            is not None
        )
        materialized = tuple(results)
        log_timing(
            _LOGGER,
            "Materialized loaded graph-section input canvas bindings",
            started_at=started_at,
            workflow_id=workflow_id,
            section_key=section_key,
            materialization_result_count=len(materialized),
            image_endpoint_count=len(plan.image_endpoints),
            synthetic_surface_count=len(synthetic_surfaces),
            level="debug",
        )
        return materialized

    def _materialize_authored_images(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow: WorkflowState,
        workflow_id: str,
        section_key: str,
        workflow_name: str,
        projects_dir: Path,
    ) -> list[InputCanvasMaterializationResult]:
        """Restore local images currently authored in the section graph."""

        results: list[InputCanvasMaterializationResult] = []
        for endpoint in self._bindings.plan(workflow, section_key).image_endpoints:
            image_path = self._graph_sections.input_value(
                workflow,
                section_key=section_key,
                node_name=endpoint.node_name,
                field_key=endpoint.field_key,
            )
            if not isinstance(image_path, str) or not image_path:
                continue
            if not looks_like_local_path(Path(image_path)):
                log_info(
                    _LOGGER,
                    "Skipped graph input image because it is not a local filesystem path",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    section_key=section_key,
                    image_node_name=endpoint.node_name,
                    image_path=image_path,
                )
                continue
            result = self._images.materialize_input_image(
                workflows=workflows,
                workflow_id=workflow_id,
                cube_alias=section_key,
                image_node_name=endpoint.node_name,
                image_path=image_path,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
            )
            if result.image_id is not None:
                results.append(result)
        return results

    def _materialize_synthetic_surface(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow: WorkflowState,
        workflow_id: str,
        surface: InputCanvasSurface,
        workflow_name: str,
        projects_dir: Path,
    ) -> InputCanvasMaterializationResult:
        """Materialize authored masks over one app-owned backing surface."""

        started_at = perf_counter()
        materialized = self._synthetic_surfaces.materialize(
            workflows=workflows,
            workflow_id=workflow_id,
            surface=surface,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
        )
        if materialized is None:
            return InputCanvasMaterializationResult(
                section_key=surface.section_key,
                surface_key=surface.surface_key,
                image_id=None,
            )
        return self._mask_materialization.materialize(
            workflow=workflow,
            workflow_id=workflow_id,
            section_key=surface.section_key,
            surface_key=surface.surface_key,
            bindings=self._bindings.bindings_for_image(
                workflow, surface.section_key, surface.surface_key
            ),
            image_id=materialized.image_id,
            image=materialized.image,
            associated_image_path=materialized.path,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
            started_at=started_at,
        )


__all__ = ["InputSectionMaterializationService"]
