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

"""Own app-created backing surfaces for mask-only Input canvases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from substitute.application.workflows.input_canvas_ports import (
    CanvasIoServicePort,
    InputCanvasStateServicePort,
)
from substitute.domain.workflow import (
    InputCanvasPlan,
    InputCanvasSurface,
    InputCanvasSurfaceKind,
    WorkflowState,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.workflows.synthetic_input_canvas_surface_service")


@dataclass(frozen=True, slots=True)
class MaterializedSyntheticInputSurface:
    """Describe one live app-owned canvas surface and its durable backing file."""

    surface: InputCanvasSurface
    image_id: UUID
    image: object
    path: Path


class SyntheticInputCanvasSurfaceService:
    """Create and invalidate synthetic canvas surfaces without touching graph state."""

    def __init__(
        self,
        *,
        input_canvas_state_service: InputCanvasStateServicePort,
        canvas_io_service: CanvasIoServicePort,
    ) -> None:
        """Capture the state and persistence owners used for backing surfaces."""

        self._input_canvas_state_service = input_canvas_state_service
        self._canvas_io_service = canvas_io_service

    def materialize(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        surface: InputCanvasSurface,
        workflow_name: str,
        projects_dir: Path,
    ) -> MaterializedSyntheticInputSurface | None:
        """Create and load one deterministic backing image for a synthetic surface."""

        dimensions = surface.dimensions
        if surface.kind is not InputCanvasSurfaceKind.SYNTHETIC or dimensions is None:
            return None
        surface_path = self.path_for_surface(
            surface,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
        )
        image = self._canvas_io_service.create_blank_input_surface(
            destination=surface_path,
            width=dimensions.width,
            height=dimensions.height,
        )
        if image is None:
            log_warning(
                _LOGGER,
                "Synthetic Input canvas backing image could not be materialized",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                section_key=surface.section_key,
                canvas_surface_key=surface.surface_key,
                width=dimensions.width,
                height=dimensions.height,
                surface_path=str(surface_path),
            )
            return None
        image_id = self._input_canvas_state_service.load_input_image(
            workflows,
            workflow_id,
            surface.input_key,
            image,
            surface_path,
        )
        log_info(
            _LOGGER,
            "Materialized synthetic mask-only Input canvas surface",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            section_key=surface.section_key,
            canvas_surface_key=surface.surface_key,
            image_id=str(image_id),
            width=dimensions.width,
            height=dimensions.height,
            authority_nodes=(
                surface.dimension_authority.node_names
                if surface.dimension_authority is not None
                else ()
            ),
        )
        return MaterializedSyntheticInputSurface(
            surface=surface,
            image_id=image_id,
            image=image,
            path=surface_path,
        )

    def invalidate_stale(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        workflow: WorkflowState,
        section_key: str,
        plan: InputCanvasPlan,
    ) -> tuple[str, ...]:
        """Drop synthetic surfaces whose current graph authority no longer owns them."""

        prefix = f"{section_key}:@synthetic/"
        current_keys = {
            surface.input_key
            for surface in plan.surfaces
            if surface.kind is InputCanvasSurfaceKind.SYNTHETIC
        }
        stale_keys = tuple(
            input_key
            for input_key in workflow.canvas.input_key_map
            if input_key.startswith(prefix) and input_key not in current_keys
        )
        for input_key in stale_keys:
            self._input_canvas_state_service.drop_input_surface(
                workflows,
                workflow_id,
                input_key,
            )
        if stale_keys:
            log_info(
                _LOGGER,
                "Invalidated stale synthetic Input canvas surfaces",
                workflow_id=workflow_id,
                section_key=section_key,
                stale_surface_count=len(stale_keys),
                current_surface_count=len(current_keys),
            )
        return stale_keys

    def path_for_surface(
        self,
        surface: InputCanvasSurface,
        *,
        workflow_name: str,
        projects_dir: Path,
    ) -> Path:
        """Return the deterministic backing path for one synthetic surface."""

        dimensions = surface.dimensions
        if surface.kind is not InputCanvasSurfaceKind.SYNTHETIC or dimensions is None:
            raise ValueError("Synthetic surface dimensions are required")
        return self._canvas_io_service.synthetic_input_surface_path(
            workflow_name=workflow_name,
            section_key=surface.section_key,
            surface_key=surface.surface_key,
            width=dimensions.width,
            height=dimensions.height,
            projects_dir=projects_dir,
        )


__all__ = [
    "MaterializedSyntheticInputSurface",
    "SyntheticInputCanvasSurfaceService",
]
