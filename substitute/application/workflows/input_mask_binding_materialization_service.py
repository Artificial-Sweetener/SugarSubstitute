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

"""Coordinate scalar and ordered mask materialization for one Input surface."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from uuid import UUID

from substitute.application.workflows.input_canvas_models import (
    InputCanvasMaterializationResult,
    MaskMaterializationResult,
)
from substitute.application.workflows.input_mask_materialization_service import (
    InputMaskMaterializationService,
)
from substitute.application.workflows.ordered_mask_materialization_service import (
    OrderedMaskMaterializationService,
)
from substitute.domain.workflow import (
    InputAssetCardinality,
    InputCanvasMaskBinding,
    WorkflowState,
)
from substitute.shared.logging.logger import get_logger, log_timing, log_warning

_LOGGER = get_logger("application.workflows.input_mask_binding_materialization_service")


class InputMaskBindingMaterializationService:
    """Materialize every scalar or ordered mask binding for one canvas surface."""

    def __init__(
        self,
        *,
        scalar_service: InputMaskMaterializationService,
        ordered_service: OrderedMaskMaterializationService,
    ) -> None:
        """Capture the cardinality-specific materialization owners."""

        self._scalar_service = scalar_service
        self._ordered_service = ordered_service

    def materialize(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        section_key: str,
        surface_key: str,
        bindings: tuple[InputCanvasMaskBinding, ...],
        image_id: UUID,
        image: object,
        associated_image_path: Path,
        workflow_name: str,
        projects_dir: Path,
        started_at: float | None = None,
    ) -> InputCanvasMaterializationResult:
        """Return one surface result containing all successfully materialized masks."""

        operation_started_at = started_at or perf_counter()
        mask_results: list[MaskMaterializationResult] = []
        for binding in bindings:
            phase_started_at = perf_counter()
            if binding.mask_endpoint.cardinality is InputAssetCardinality.ORDERED:
                materialized = self._ordered_service.materialize(
                    workflow=workflow,
                    workflow_id=workflow_id,
                    binding=binding,
                    image_id=image_id,
                    image=image,
                    associated_image_path=associated_image_path,
                    workflow_name=workflow_name,
                    projects_dir=projects_dir,
                )
            else:
                scalar = self._scalar_service.materialize(
                    workflow=workflow,
                    workflow_id=workflow_id,
                    binding=binding,
                    image_id=image_id,
                    image=image,
                    associated_image_path=associated_image_path,
                    workflow_name=workflow_name,
                    projects_dir=projects_dir,
                )
                materialized = () if scalar is None else (scalar,)
            mask_results.extend(materialized)
            log_timing(
                _LOGGER,
                "Materialized editable mask binding",
                started_at=phase_started_at,
                workflow_id=workflow_id,
                section_key=binding.section_key,
                canvas_surface_key=binding.surface_key,
                mask_node_name=binding.mask_node_name,
                cardinality=binding.mask_endpoint.cardinality.value,
                materialized_count=len(materialized),
                level="debug",
            )
        if bindings and not mask_results:
            log_warning(
                _LOGGER,
                "Editable mask bindings resolved but no input canvas masks materialized",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                section_key=section_key,
                surface_key=surface_key,
                image_id=str(image_id),
                binding_count=len(bindings),
            )
        result = InputCanvasMaterializationResult(
            section_key=section_key,
            surface_key=surface_key,
            image_id=image_id,
            mask_results=tuple(mask_results),
        )
        log_timing(
            _LOGGER,
            "Materialized input image and editable masks",
            started_at=operation_started_at,
            workflow_id=workflow_id,
            section_key=section_key,
            surface_key=surface_key,
            mask_result_count=len(mask_results),
            level="debug",
        )
        return result


__all__ = ["InputMaskBindingMaterializationService"]
