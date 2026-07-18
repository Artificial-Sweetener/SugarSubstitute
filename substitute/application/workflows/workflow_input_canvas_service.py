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

"""Own editable input-canvas image and mask binding lifecycle for workflows."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Mapping
from uuid import UUID

from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.input_canvas_models import (
    InputCanvasMaterializationResult,
    LoadedInputCanvasImageIdentityResolution,
    MaskMaterializationResult,
    UserSelectedInputMaskResult,
)
from substitute.application.workflows.input_canvas_ports import (
    CanvasIoServicePort,
    InputCanvasStateServicePort,
    WorkflowAssetServicePort,
)
from substitute.application.workflows.input_mask_materialization_service import (
    InputMaskMaterializationService,
)
from substitute.application.workflows.synthetic_input_canvas_surface_service import (
    SyntheticInputCanvasSurfaceService,
)
from substitute.application.workflows.workflow_asset_service import WorkflowAssetService
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import (
    InputCanvasMaskBinding,
    InputCanvasPlan,
    InputCanvasSurface,
    InputCanvasSurfaceKind,
    WorkflowAssetRef,
    WorkflowState,
)
from substitute.shared.logging.logger import (
    log_debug,
    get_logger,
    log_info,
    log_timing,
    log_warning,
)

_LOGGER = get_logger("application.workflows.workflow_input_canvas_service")


class WorkflowInputCanvasService:
    """Own graph-driven input canvas reconciliation for one workflow."""

    def __init__(
        self,
        *,
        input_canvas_plan_service: InputCanvasPlanService,
        input_canvas_state_service: InputCanvasStateServicePort,
        canvas_io_service: CanvasIoServicePort,
        workflow_asset_service: WorkflowAssetServicePort | None = None,
        graph_section_service: WorkflowGraphSectionService | None = None,
    ) -> None:
        """Capture collaborators used for binding discovery, state, and IO."""

        self._input_canvas_plan_service = input_canvas_plan_service
        self._input_canvas_state_service = input_canvas_state_service
        self._canvas_io_service = canvas_io_service
        self._graph_section_service = (
            graph_section_service or WorkflowGraphSectionService()
        )
        self._workflow_asset_service = workflow_asset_service or WorkflowAssetService(
            self._graph_section_service
        )
        self._mask_materialization_service = InputMaskMaterializationService(
            input_canvas_state_service=input_canvas_state_service,
            canvas_io_service=canvas_io_service,
            workflow_asset_service=self._workflow_asset_service,
            graph_section_service=self._graph_section_service,
        )
        self._synthetic_surface_service = SyntheticInputCanvasSurfaceService(
            input_canvas_state_service=input_canvas_state_service,
            canvas_io_service=canvas_io_service,
        )

    def bindings_for_image(
        self,
        workflow: WorkflowState,
        section_key: str,
        image_node_name: str,
    ) -> tuple[InputCanvasMaskBinding, ...]:
        """Return editable mask bindings for one workflow image node."""

        return self._canvas_plan_for_section(
            workflow, section_key
        ).bindings_for_surface_key(image_node_name)

    def binding_for_mask(
        self,
        workflow: WorkflowState,
        section_key: str,
        mask_node_name: str,
    ) -> InputCanvasMaskBinding | None:
        """Return editable mask binding for one workflow mask node when present."""

        return self._canvas_plan_for_section(workflow, section_key).binding_for_mask(
            mask_node_name
        )

    def associate_project_input_mask(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Persist a project mask through its discovered upload widget field."""

        binding = self.binding_for_mask(workflow, section_key, node_name)
        if binding is None:
            return False
        return self._workflow_asset_service.associate_project_input_mask(
            workflow,
            section_key=section_key,
            node_name=node_name,
            field_key=binding.mask_field_key,
            relative_path=relative_path,
        )

    def input_image_asset_ref(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
    ) -> WorkflowAssetRef | None:
        """Return an image asset through its discovered upload widget field."""

        endpoint = self._canvas_plan_for_section(
            workflow, section_key
        ).image_endpoint_for_node(node_name)
        if endpoint is None:
            return None
        return self._workflow_asset_service.input_image_asset_ref(
            workflow,
            section_key=section_key,
            node_name=node_name,
            field_key=endpoint.field_key,
        )

    def input_mask_asset_ref(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
    ) -> WorkflowAssetRef | None:
        """Return a mask asset through its discovered upload widget field."""

        binding = self.binding_for_mask(workflow, section_key, node_name)
        if binding is None:
            return None
        return self._workflow_asset_service.input_mask_asset_ref(
            workflow,
            section_key=section_key,
            node_name=node_name,
            field_key=binding.mask_field_key,
        )

    def resolve_input_mask_path(
        self,
        workflow: WorkflowState,
        *,
        workflow_name: str,
        section_key: str,
        node_name: str,
        projects_dir: Path,
    ) -> Path | None:
        """Resolve a mask asset through its discovered upload widget field."""

        binding = self.binding_for_mask(workflow, section_key, node_name)
        if binding is None:
            return None
        return self._workflow_asset_service.resolve_input_mask_path(
            workflow,
            workflow_name=workflow_name,
            section_key=section_key,
            node_name=node_name,
            field_key=binding.mask_field_key,
            projects_dir=projects_dir,
        )

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
        """Validate and apply one user-selected mask file through Input ownership."""

        workflow = workflows.get(workflow_id)
        if workflow is None or not mask_path:
            return UserSelectedInputMaskResult.rejected(
                "missing_workflow_or_mask_path",
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
            )

        binding = self.binding_for_mask(workflow, cube_alias, mask_node_name)
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

        input_key = binding.surface.input_key
        image_id = workflow.canvas.input_key_map.get(input_key)
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
                input_key=input_key,
                rejection_reason="missing_bound_input_image",
            )
            return UserSelectedInputMaskResult.rejected(
                "missing_bound_input_image",
                cube_alias=cube_alias,
                node_name=mask_node_name,
                mask_path=mask_path,
            )

        image_dimensions = self._canvas_io_service.image_dimensions(Path(image_path))
        mask_dimensions = self._canvas_io_service.image_dimensions(Path(mask_path))
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
        mask_id = workflow.canvas.mask_associations.get(association_key)
        if mask_id is None:
            image = self._canvas_io_service.load_input_image(Path(image_path))
            if image is not None:
                self._input_canvas_state_service.claim_loaded_input_image(
                    workflow_id,
                    workflow,
                    binding.surface.input_key,
                    image_id,
                )
                materialization_result = self._materialize_bound_masks_for_image(
                    workflow=workflow,
                    workflow_id=workflow_id,
                    cube_alias=binding.section_key,
                    image_node_name=binding.surface_key,
                    image_id=image_id,
                    image=image,
                    associated_image_path=Path(image_path),
                    workflow_name=workflow_name,
                    projects_dir=projects_dir,
                    started_at=perf_counter(),
                )
            mask_id = workflow.canvas.mask_associations.get(association_key)
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

        updated = self._input_canvas_state_service.update_mask_from_file(
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
                "Rejected user-selected input mask because canvas mask pixels were not updated",
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

        associated = self._workflow_asset_service.associate_local_input_mask(
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

    def unambiguous_bound_image_identity(
        self,
        workflow: WorkflowState,
    ) -> tuple[str, str] | None:
        """Return the only graph-bound input image identity in a workflow."""

        identities: list[tuple[str, str]] = []
        for section_key in self._graph_section_service.section_keys(workflow):
            plan = self._canvas_plan_for_section(workflow, section_key)
            identities.extend(endpoint.identity for endpoint in plan.image_endpoints)
        unique_identities = tuple(dict.fromkeys(identities))
        if len(unique_identities) != 1:
            return None
        return unique_identities[0]

    def resolve_loaded_input_canvas_image_identity(
        self,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> LoadedInputCanvasImageIdentityResolution:
        """Resolve a QPane-loaded image UUID to a workflow input image node."""

        mapped_input_key = self._input_key_for_image_id(workflow, image_id)
        if mapped_input_key is not None:
            parsed = self._parse_input_key(mapped_input_key)
            if parsed is None:
                return LoadedInputCanvasImageIdentityResolution.rejected(
                    "malformed_input_key",
                    input_key=mapped_input_key,
                )
            cube_alias, image_node_name = parsed
            return LoadedInputCanvasImageIdentityResolution.mapped(
                cube_alias=cube_alias,
                image_node_name=image_node_name,
            )

        fallback_identity = self.unambiguous_bound_image_identity(workflow)
        if fallback_identity is None:
            return LoadedInputCanvasImageIdentityResolution.rejected(
                "unmapped_image_id"
            )
        cube_alias, image_node_name = fallback_identity
        return LoadedInputCanvasImageIdentityResolution.mapped(
            cube_alias=cube_alias,
            image_node_name=image_node_name,
        )

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
            return InputCanvasMaterializationResult(
                section_key=cube_alias,
                surface_key=image_node_name,
                image_id=None,
            )
        endpoint = self._canvas_plan_for_section(
            workflow, cube_alias
        ).image_endpoint_for_node(image_node_name)
        if endpoint is None:
            log_warning(
                _LOGGER,
                "Rejected input image without an unambiguous upload endpoint",
                workflow_id=workflow_id,
                section_key=cube_alias,
                image_node_name=image_node_name,
            )
            return InputCanvasMaterializationResult(
                section_key=cube_alias,
                surface_key=image_node_name,
                image_id=None,
            )

        resolved_image_path = Path(image_path)
        associated = self._workflow_asset_service.associate_local_input_image(
            workflow,
            section_key=cube_alias,
            node_name=image_node_name,
            field_key=endpoint.field_key,
            image_path=resolved_image_path,
        )
        log_debug(
            _LOGGER,
            "Associated selected input image with workflow asset state",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            image_path=str(resolved_image_path),
            association_succeeded=associated,
        )
        phase_started_at = perf_counter()
        image = self._canvas_io_service.load_input_image(resolved_image_path)
        log_timing(
            _LOGGER,
            "Loaded input image for canvas materialization",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            path=str(resolved_image_path),
            level="debug",
        )
        is_null = getattr(image, "isNull", None)
        if image is None or (callable(is_null) and bool(is_null())):
            log_function = (
                log_warning if _looks_like_local_path(resolved_image_path) else log_info
            )
            log_function(
                _LOGGER,
                "Failed to load input image for canvas reconciliation",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                node_name=image_node_name,
                path=str(resolved_image_path),
            )
            return InputCanvasMaterializationResult(
                section_key=cube_alias,
                surface_key=image_node_name,
                image_id=None,
            )

        input_key = f"{cube_alias}:{image_node_name}"
        phase_started_at = perf_counter()
        image_id = self._input_canvas_state_service.load_input_image(
            dict(workflows),
            workflow_id,
            input_key,
            image,
            resolved_image_path,
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
            return InputCanvasMaterializationResult(
                section_key=cube_alias,
                surface_key=image_node_name,
                image_id=None,
            )

        return self._materialize_bound_masks_for_image(
            workflow=workflow,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            image_id=image_id,
            image=image,
            associated_image_path=resolved_image_path,
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
        """Associate an existing input-canvas image, then reconcile editable masks."""

        started_at = perf_counter()
        workflow = workflows.get(workflow_id)
        if workflow is None or not image_path:
            return InputCanvasMaterializationResult(
                section_key=cube_alias,
                surface_key=image_node_name,
                image_id=None,
            )
        endpoint = self._canvas_plan_for_section(
            workflow, cube_alias
        ).image_endpoint_for_node(image_node_name)
        if endpoint is None:
            return InputCanvasMaterializationResult(
                section_key=cube_alias,
                surface_key=image_node_name,
                image_id=None,
            )

        resolved_image_path = Path(image_path)
        associated = self._workflow_asset_service.associate_local_input_image(
            workflow,
            section_key=cube_alias,
            node_name=image_node_name,
            field_key=endpoint.field_key,
            image_path=resolved_image_path,
        )
        input_key = f"{cube_alias}:{image_node_name}"
        claimed = self._input_canvas_state_service.claim_loaded_input_image(
            workflow_id,
            workflow,
            input_key,
            image_id,
        )
        if not claimed:
            return InputCanvasMaterializationResult(
                section_key=cube_alias,
                surface_key=image_node_name,
                image_id=None,
            )
        log_debug(
            _LOGGER,
            "Associated existing input-canvas image with workflow asset state",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            image_id=image_id,
            image_path=str(resolved_image_path),
            input_key=input_key,
            association_succeeded=associated,
        )

        phase_started_at = perf_counter()
        image = self._canvas_io_service.load_input_image(resolved_image_path)
        log_timing(
            _LOGGER,
            "Loaded existing input-canvas image for mask reconciliation",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            image_id=image_id,
            path=str(resolved_image_path),
            level="debug",
        )
        is_null = getattr(image, "isNull", None)
        if image is None or (callable(is_null) and bool(is_null())):
            log_warning(
                _LOGGER,
                "Failed to load existing input-canvas image for mask reconciliation",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                image_node_name=image_node_name,
                image_id=image_id,
                path=str(resolved_image_path),
            )
            return InputCanvasMaterializationResult(
                section_key=cube_alias,
                surface_key=image_node_name,
                image_id=image_id,
            )

        return self._materialize_bound_masks_for_image(
            workflow=workflow,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            image_id=image_id,
            image=image,
            associated_image_path=resolved_image_path,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
            started_at=started_at,
        )

    def _materialize_bound_masks_for_image(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        cube_alias: str,
        image_node_name: str,
        image_id: UUID,
        image: object,
        associated_image_path: Path,
        workflow_name: str,
        projects_dir: Path,
        started_at: float,
    ) -> InputCanvasMaterializationResult:
        """Reconcile every editable mask binding for one loaded input image."""

        mask_results: list[MaskMaterializationResult] = []
        phase_started_at = perf_counter()
        bindings = self.bindings_for_image(workflow, cube_alias, image_node_name)
        log_timing(
            _LOGGER,
            "Resolved editable mask bindings for input image",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            binding_count=len(bindings),
            level="debug",
        )
        for binding in bindings:
            phase_started_at = perf_counter()
            materialized = self._mask_materialization_service.materialize(
                workflow=workflow,
                workflow_id=workflow_id,
                binding=binding,
                image_id=image_id,
                image=image,
                associated_image_path=associated_image_path,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
            )
            log_timing(
                _LOGGER,
                "Materialized editable mask binding",
                started_at=phase_started_at,
                workflow_id=workflow_id,
                section_key=binding.section_key,
                canvas_surface_key=binding.surface_key,
                mask_node_name=binding.mask_node_name,
                materialized=materialized is not None,
                source=materialized.source if materialized is not None else "",
                level="debug",
            )
            if materialized is not None:
                mask_results.append(materialized)
        if bindings and not mask_results:
            log_warning(
                _LOGGER,
                "Editable mask bindings resolved but no input canvas masks materialized",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                image_node_name=image_node_name,
                image_id=str(image_id),
                binding_count=len(bindings),
                mask_result_count=0,
            )

        result = InputCanvasMaterializationResult(
            section_key=cube_alias,
            surface_key=image_node_name,
            image_id=image_id,
            mask_results=tuple(mask_results),
        )
        log_timing(
            _LOGGER,
            "Materialized input image and editable masks",
            started_at=started_at,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            mask_result_count=len(mask_results),
            level="debug",
        )
        return result

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
        """Materialize authored mask layers over one app-owned backing surface."""

        started_at = perf_counter()
        materialized = self._synthetic_surface_service.materialize(
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
        return self._materialize_bound_masks_for_image(
            workflow=workflow,
            workflow_id=workflow_id,
            cube_alias=surface.section_key,
            image_node_name=surface.surface_key,
            image_id=materialized.image_id,
            image=materialized.image,
            associated_image_path=materialized.path,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
            started_at=started_at,
        )

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
        results: list[InputCanvasMaterializationResult] = []
        phase_started_at = perf_counter()
        plan = self._canvas_plan_for_section(workflow, section_key)
        self._synthetic_surface_service.invalidate_stale(
            workflows=workflows,
            workflow_id=workflow_id,
            workflow=workflow,
            section_key=section_key,
            plan=plan,
        )
        image_endpoints = plan.image_endpoints
        synthetic_surfaces = tuple(
            surface
            for surface in plan.surfaces
            if surface.kind is InputCanvasSurfaceKind.SYNTHETIC
        )
        log_timing(
            _LOGGER,
            "Built input asset binding index for loaded graph section",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            section_key=section_key,
            image_endpoint_count=len(image_endpoints),
            synthetic_surface_count=len(synthetic_surfaces),
            level="debug",
        )
        for endpoint in image_endpoints:
            image_path = self._image_path_from_buffer(
                workflow,
                section_key,
                endpoint.node_name,
                endpoint.field_key,
            )
            if not isinstance(image_path, str) or not image_path:
                continue
            if not _looks_like_local_path(Path(image_path)):
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
            result = self.materialize_input_image(
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
        for surface in synthetic_surfaces:
            result = self._materialize_synthetic_surface(
                workflows=workflows,
                workflow=workflow,
                workflow_id=workflow_id,
                surface=surface,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
            )
            if result.image_id is not None:
                results.append(result)
        materialized_results = tuple(results)
        log_timing(
            _LOGGER,
            "Materialized loaded graph-section input canvas bindings",
            started_at=started_at,
            workflow_id=workflow_id,
            section_key=section_key,
            materialization_result_count=len(materialized_results),
            image_endpoint_count=len(image_endpoints),
            synthetic_surface_count=len(synthetic_surfaces),
            level="debug",
        )
        return materialized_results

    def _canvas_plan_for_section(
        self,
        workflow: WorkflowState,
        section_key: str,
    ) -> InputCanvasPlan:
        """Return the unified Input canvas plan for one graph section."""

        graph = self._graph_section_service.graph(workflow, section_key)
        if graph is None:
            return InputCanvasPlan(section_key=section_key)
        return self._input_canvas_plan_service.build_plan(
            section_key,
            graph,
        )

    @staticmethod
    def _input_key_for_image_id(
        workflow: WorkflowState,
        image_id: UUID,
    ) -> str | None:
        """Return the workflow input key currently mapped to image_id."""

        for input_key, mapped_image_id in workflow.canvas.input_key_map.items():
            if mapped_image_id == image_id:
                return input_key
        return None

    def _image_path_from_buffer(
        self,
        workflow: WorkflowState,
        section_key: str,
        node_name: str,
        field_key: str,
    ) -> str:
        """Return the current image input path from a workflow graph buffer."""

        value = self._graph_section_service.input_value(
            workflow,
            section_key=section_key,
            node_name=node_name,
            field_key=field_key,
        )
        return value if isinstance(value, str) else ""

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
            return self._image_path_from_buffer(
                workflow,
                endpoint.section_key,
                endpoint.node_name,
                endpoint.field_key,
            )
        dimensions = surface.dimensions
        if surface.kind is not InputCanvasSurfaceKind.SYNTHETIC or dimensions is None:
            return ""
        return str(
            self._synthetic_surface_service.path_for_surface(
                surface,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
            )
        )

    @staticmethod
    def _parse_input_key(input_key: str) -> tuple[str, str] | None:
        """Parse the durable graph-section/node input image key."""

        cube_alias, separator, image_node_name = input_key.partition(":")
        if not cube_alias or separator != ":" or not image_node_name:
            return None
        return (cube_alias, image_node_name)


def _looks_like_local_path(path: Path) -> bool:
    """Return whether a path value appears intended as a filesystem path."""

    path_text = str(path)
    return path.is_absolute() or "\\" in path_text or "/" in path_text


__all__ = [
    "InputCanvasMaterializationResult",
    "LoadedInputCanvasImageIdentityResolution",
    "MaskMaterializationResult",
    "UserSelectedInputMaskResult",
    "WorkflowInputCanvasService",
]
