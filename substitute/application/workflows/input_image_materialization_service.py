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

"""Materialize graph-backed input images and their bound mask layers."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Mapping
from uuid import UUID

from substitute.application.workflows.input_canvas_binding_service import (
    InputCanvasBindingService,
)
from substitute.application.workflows.input_canvas_models import (
    InputCanvasMaterializationResult,
)
from substitute.application.workflows.input_canvas_ports import (
    CanvasIoServicePort,
    WorkflowAssetServicePort,
)
from substitute.application.workflows.input_image_asset_service import (
    InputImageAssetService,
)
from substitute.application.workflows.input_mask_binding_materialization_service import (
    InputMaskBindingMaterializationService,
)
from substitute.application.workflows.workflow_asset_service import WorkflowAssetService
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_timing,
    log_warning,
)

_LOGGER = get_logger("application.workflows.input_image_materialization_service")


class InputImageMaterializationService:
    """Own graph association and canvas materialization for input images."""

    def __init__(
        self,
        *,
        bindings: InputCanvasBindingService,
        images: InputImageAssetService,
        canvas_io: CanvasIoServicePort,
        mask_materialization: InputMaskBindingMaterializationService,
        workflow_assets: WorkflowAssetServicePort | None = None,
        graph_sections: WorkflowGraphSectionService | None = None,
    ) -> None:
        """Store binding, image-state, IO, and bound-mask owners."""

        self._bindings = bindings
        self._images = images
        self._canvas_io = canvas_io
        self._graph_sections = graph_sections or WorkflowGraphSectionService()
        self._workflow_assets = workflow_assets or WorkflowAssetService(
            self._graph_sections
        )
        self._mask_materialization = mask_materialization

    def materialize_input_image(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        cube_alias: str,
        image_node_name: str,
        image_path: str,
        workflow_name: str,
        projects_dir: Path,
    ) -> InputCanvasMaterializationResult:
        """Load one input image and reconcile all editable bound mask layers."""

        started_at = perf_counter()
        workflow = workflows.get(workflow_id)
        if workflow is None or not image_path:
            return _empty_result(cube_alias, image_node_name)
        endpoint = self._bindings.plan(workflow, cube_alias).image_endpoint_for_node(
            image_node_name
        )
        if endpoint is None:
            log_warning(
                _LOGGER,
                "Rejected input image without an unambiguous upload endpoint",
                workflow_id=workflow_id,
                section_key=cube_alias,
                image_node_name=image_node_name,
            )
            return _empty_result(cube_alias, image_node_name)

        resolved_path = Path(image_path)
        associated = self._workflow_assets.associate_local_input_image(
            workflow,
            section_key=cube_alias,
            node_name=image_node_name,
            field_key=endpoint.field_key,
            image_path=resolved_path,
        )
        log_debug(
            _LOGGER,
            "Associated selected input image with workflow asset state",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            image_path=str(resolved_path),
            association_succeeded=associated,
        )
        phase_started_at = perf_counter()
        image = self._canvas_io.load_input_image(resolved_path)
        log_timing(
            _LOGGER,
            "Loaded input image for canvas materialization",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            path=str(resolved_path),
            level="debug",
        )
        if _image_is_null(image):
            log_function = (
                log_warning if looks_like_local_path(resolved_path) else log_info
            )
            log_function(
                _LOGGER,
                "Failed to load input image for canvas reconciliation",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                node_name=image_node_name,
                path=str(resolved_path),
            )
            return _empty_result(cube_alias, image_node_name)

        input_key = f"{cube_alias}:{image_node_name}"
        phase_started_at = perf_counter()
        image_id = self._images.load(
            dict(workflows), workflow_id, input_key, image, resolved_path
        )
        log_timing(
            _LOGGER,
            "Inserted loaded input image into canvas state",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            input_key=input_key,
            image_id=image_id,
            level="debug",
        )
        if image_id is None:
            return _empty_result(cube_alias, image_node_name)
        return self._materialize_bound_masks(
            workflow=workflow,
            workflow_id=workflow_id,
            section_key=cube_alias,
            surface_key=image_node_name,
            image_id=image_id,
            image=image,
            image_path=resolved_path,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
            started_at=started_at,
        )

    def reconcile_loaded_input_canvas_image(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        cube_alias: str,
        image_node_name: str,
        image_id: UUID,
        image_path: str,
        workflow_name: str,
        projects_dir: Path,
    ) -> InputCanvasMaterializationResult:
        """Associate an existing input-canvas image, then reconcile its masks."""

        started_at = perf_counter()
        workflow = workflows.get(workflow_id)
        if workflow is None or not image_path:
            return _empty_result(cube_alias, image_node_name)
        endpoint = self._bindings.plan(workflow, cube_alias).image_endpoint_for_node(
            image_node_name
        )
        if endpoint is None:
            return _empty_result(cube_alias, image_node_name)

        resolved_path = Path(image_path)
        associated = self._workflow_assets.associate_local_input_image(
            workflow,
            section_key=cube_alias,
            node_name=image_node_name,
            field_key=endpoint.field_key,
            image_path=resolved_path,
        )
        input_key = f"{cube_alias}:{image_node_name}"
        if not self._images.claim_loaded(workflow_id, workflow, input_key, image_id):
            return _empty_result(cube_alias, image_node_name)
        log_debug(
            _LOGGER,
            "Associated existing input-canvas image with workflow asset state",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            image_id=image_id,
            image_path=str(resolved_path),
            input_key=input_key,
            association_succeeded=associated,
        )
        phase_started_at = perf_counter()
        image = self._canvas_io.load_input_image(resolved_path)
        log_timing(
            _LOGGER,
            "Loaded existing input-canvas image for mask reconciliation",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            image_id=image_id,
            path=str(resolved_path),
            level="debug",
        )
        if _image_is_null(image):
            log_warning(
                _LOGGER,
                "Failed to load existing input-canvas image for mask reconciliation",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                image_node_name=image_node_name,
                image_id=image_id,
                path=str(resolved_path),
            )
            return InputCanvasMaterializationResult(
                section_key=cube_alias,
                surface_key=image_node_name,
                image_id=image_id,
            )
        return self._materialize_bound_masks(
            workflow=workflow,
            workflow_id=workflow_id,
            section_key=cube_alias,
            surface_key=image_node_name,
            image_id=image_id,
            image=image,
            image_path=resolved_path,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
            started_at=started_at,
        )

    def _materialize_bound_masks(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        section_key: str,
        surface_key: str,
        image_id: UUID,
        image: object,
        image_path: Path,
        workflow_name: str,
        projects_dir: Path,
        started_at: float,
    ) -> InputCanvasMaterializationResult:
        """Delegate bound masks to the cardinality-aware materialization owner."""

        return self._mask_materialization.materialize(
            workflow=workflow,
            workflow_id=workflow_id,
            section_key=section_key,
            surface_key=surface_key,
            bindings=self._bindings.bindings_for_image(
                workflow, section_key, surface_key
            ),
            image_id=image_id,
            image=image,
            associated_image_path=image_path,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
            started_at=started_at,
        )


def looks_like_local_path(path: Path) -> bool:
    """Return whether a path value appears intended as a filesystem path."""

    path_text = str(path)
    return path.is_absolute() or "\\" in path_text or "/" in path_text


def _image_is_null(image: object | None) -> bool:
    """Return whether an image repository result is absent or null."""

    if image is None:
        return True
    is_null = getattr(image, "isNull", None)
    return callable(is_null) and bool(is_null())


def _empty_result(
    section_key: str, surface_key: str
) -> InputCanvasMaterializationResult:
    """Build an unsuccessful materialization result for one surface."""

    return InputCanvasMaterializationResult(
        section_key=section_key,
        surface_key=surface_key,
        image_id=None,
    )


__all__ = ["InputImageMaterializationService", "looks_like_local_path"]
