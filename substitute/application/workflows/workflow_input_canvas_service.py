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

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Mapping, Protocol
from uuid import UUID

from substitute.application.cubes.cube_mask_binding_service import (
    CubeMaskBindingService,
)
from substitute.application.workflows.workflow_asset_service import WorkflowAssetService
from substitute.domain.workflow import (
    EditableMaskBinding,
    EditableMaskBindingIndex,
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


class _InputCanvasStateServicePort(Protocol):
    """Describe Input canvas state capabilities used by graph reconciliation."""

    def load_input_image(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
        input_key: str,
        image: object,
        path: Path,
    ) -> UUID:
        """Load one input image and return its live canvas UUID."""

    def load_mask_from_file(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        path: Path,
    ) -> UUID | None:
        """Load one mask from disk for an explicit target image."""

    def create_mask_for_image(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        size: object,
    ) -> UUID | None:
        """Create one blank mask for an explicit target image."""

    def set_active_input_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> bool:
        """Persist and project one active Input image."""

    def claim_loaded_input_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        input_key: str,
        image_id: UUID,
    ) -> bool:
        """Claim an existing QPane-loaded image for a workflow input key."""

    def drop_mask_association(
        self,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
    ) -> None:
        """Drop one stale mask association from canvas state and pane state."""

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
        """Update one associated mask layer after Input ownership validation."""


class _CanvasIoServicePort(Protocol):
    """Describe canvas IO capabilities used by workflow input reconciliation."""

    def load_input_image(self, path: Path) -> object | None:
        """Load one input image from disk."""

    def expected_bound_mask_path(
        self,
        *,
        workflow_name: str,
        associated_image_path: Path,
        cube_alias: str,
        mask_node_name: str,
        image_size: tuple[int, int] | None,
        projects_dir: Path,
    ) -> Path:
        """Return the expected input-image-bound mask path."""

    def allocate_bound_mask_path(
        self,
        *,
        workflow_name: str,
        associated_image_path: Path,
        cube_alias: str,
        mask_node_name: str,
        image_size: tuple[int, int] | None,
        projects_dir: Path,
    ) -> Path:
        """Allocate one collision-safe input-image-bound mask path."""

    def image_dimensions(self, path: Path) -> tuple[int, int] | None:
        """Return image dimensions for a filesystem image."""

    def resolve_mask_path(
        self,
        *,
        workflow_name: str,
        path_from_buffer: str,
        projects_dir: Path,
    ) -> Path:
        """Resolve a previous mask buffer path for compatibility checks."""

    def create_blank_mask(self, *, destination: Path, size: object) -> bool:
        """Persist one blank mask file to disk."""


class _WorkflowAssetServicePort(Protocol):
    """Describe asset ownership writes used by mask materialization."""

    def associate_local_input_image(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        image_path: Path | str,
    ) -> bool:
        """Associate one input image node with a user-selected local image file."""

    def associate_local_input_mask(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        mask_path: Path | str,
    ) -> bool:
        """Associate one input mask node with a user-selected local mask file."""

    def associate_project_input_mask(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Associate one input mask node with a project mask asset."""

    def input_mask_asset_ref(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
    ) -> WorkflowAssetRef | None:
        """Return durable asset metadata for one input mask node when present."""

    def resolve_input_mask_path(
        self,
        workflow: WorkflowState,
        *,
        workflow_name: str,
        cube_alias: str,
        node_name: str,
        projects_dir: Path,
    ) -> Path | None:
        """Resolve one input mask node from durable asset metadata."""


@dataclass(frozen=True)
class MaskMaterializationResult:
    """Describe one mask layer materialized for an input image binding."""

    association_key: tuple[str, str]
    image_id: UUID
    mask_id: UUID
    resolved_path: Path
    source: str


@dataclass(frozen=True)
class InputCanvasMaterializationResult:
    """Describe one input image load plus any materialized bound masks."""

    cube_alias: str
    image_node_name: str
    image_id: UUID | None
    mask_results: tuple[MaskMaterializationResult, ...] = ()

    @property
    def first_mask_id(self) -> UUID | None:
        """Return the first materialized mask identifier when available."""

        if not self.mask_results:
            return None
        return self.mask_results[0].mask_id


@dataclass(frozen=True)
class UserSelectedInputMaskResult:
    """Describe application handling for one user-selected mask file."""

    applied: bool
    rejection_reason: str = ""
    cube_alias: str = ""
    node_name: str = ""
    mask_path: str = ""
    selected_dimensions: tuple[int, int] | None = None
    required_dimensions: tuple[int, int] | None = None
    materialization_result: InputCanvasMaterializationResult | None = None

    @classmethod
    def rejected(
        cls,
        reason: str,
        *,
        cube_alias: str,
        node_name: str,
        mask_path: str,
        selected_dimensions: tuple[int, int] | None = None,
        required_dimensions: tuple[int, int] | None = None,
    ) -> "UserSelectedInputMaskResult":
        """Return a rejected selected-mask application result."""

        return cls(
            applied=False,
            rejection_reason=reason,
            cube_alias=cube_alias,
            node_name=node_name,
            mask_path=mask_path,
            selected_dimensions=selected_dimensions,
            required_dimensions=required_dimensions,
        )

    @classmethod
    def accepted(
        cls,
        *,
        cube_alias: str,
        node_name: str,
        mask_path: str,
        materialization_result: InputCanvasMaterializationResult | None,
    ) -> "UserSelectedInputMaskResult":
        """Return a successful selected-mask application result."""

        return cls(
            applied=True,
            cube_alias=cube_alias,
            node_name=node_name,
            mask_path=mask_path,
            materialization_result=materialization_result,
        )


@dataclass(frozen=True)
class LoadedInputCanvasImageIdentityResolution:
    """Describe how an existing QPane image maps to a workflow input node."""

    cube_alias: str | None
    image_node_name: str | None
    input_key: str | None
    rejection_reason: str | None = None

    @property
    def accepted(self) -> bool:
        """Return whether the loaded image has a concrete graph input identity."""

        return (
            self.cube_alias is not None
            and self.image_node_name is not None
            and self.input_key is not None
            and self.rejection_reason is None
        )

    @classmethod
    def mapped(
        cls,
        *,
        cube_alias: str,
        image_node_name: str,
    ) -> "LoadedInputCanvasImageIdentityResolution":
        """Return a graph identity resolved from workflow input state."""

        return cls(
            cube_alias=cube_alias,
            image_node_name=image_node_name,
            input_key=f"{cube_alias}:{image_node_name}",
        )

    @classmethod
    def rejected(
        cls,
        reason: str,
        *,
        input_key: str | None = None,
    ) -> "LoadedInputCanvasImageIdentityResolution":
        """Return a rejected graph identity lookup."""

        return cls(
            cube_alias=None,
            image_node_name=None,
            input_key=input_key,
            rejection_reason=reason,
        )


class WorkflowInputCanvasService:
    """Own graph-driven input canvas reconciliation for one workflow."""

    def __init__(
        self,
        *,
        cube_mask_binding_service: CubeMaskBindingService,
        input_canvas_state_service: _InputCanvasStateServicePort,
        canvas_io_service: _CanvasIoServicePort,
        workflow_asset_service: _WorkflowAssetServicePort | None = None,
    ) -> None:
        """Capture collaborators used for binding discovery, state, and IO."""

        self._cube_mask_binding_service = cube_mask_binding_service
        self._input_canvas_state_service = input_canvas_state_service
        self._canvas_io_service = canvas_io_service
        self._workflow_asset_service = workflow_asset_service or WorkflowAssetService()

    def bindings_for_image(
        self,
        workflow: WorkflowState,
        cube_alias: str,
        image_node_name: str,
    ) -> tuple[EditableMaskBinding, ...]:
        """Return editable mask bindings for one workflow image node."""

        return self._binding_index_for_cube(workflow, cube_alias).bindings_for_image(
            cube_alias,
            image_node_name,
        )

    def binding_for_mask(
        self,
        workflow: WorkflowState,
        cube_alias: str,
        mask_node_name: str,
    ) -> EditableMaskBinding | None:
        """Return editable mask binding for one workflow mask node when present."""

        return self._binding_index_for_cube(workflow, cube_alias).binding_for_mask(
            cube_alias,
            mask_node_name,
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

        input_key = f"{binding.cube_alias}:{binding.image_node_name}"
        image_id = workflow.canvas.input_key_map.get(input_key)
        image_path = self._image_path_from_buffer(
            workflow,
            binding.cube_alias,
            binding.image_node_name,
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
            materialization_result = self.reconcile_loaded_input_canvas_image(
                workflows=workflows,
                workflow_id=workflow_id,
                cube_alias=binding.cube_alias,
                image_node_name=binding.image_node_name,
                image_id=image_id,
                image_path=image_path,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
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
            cube_alias=cube_alias,
            node_name=mask_node_name,
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
        ordered_aliases = list(workflow.stack_order)
        ordered_aliases.extend(
            alias for alias in workflow.cubes if alias not in ordered_aliases
        )
        for cube_alias in ordered_aliases:
            identities.extend(
                self._binding_index_for_cube(workflow, cube_alias).image_identities()
            )
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
                cube_alias=cube_alias,
                image_node_name=image_node_name,
                image_id=None,
            )

        resolved_image_path = Path(image_path)
        associated = self._workflow_asset_service.associate_local_input_image(
            workflow,
            cube_alias=cube_alias,
            node_name=image_node_name,
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
                cube_alias=cube_alias,
                image_node_name=image_node_name,
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
                cube_alias=cube_alias,
                image_node_name=image_node_name,
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
                cube_alias=cube_alias,
                image_node_name=image_node_name,
                image_id=None,
            )

        resolved_image_path = Path(image_path)
        associated = self._workflow_asset_service.associate_local_input_image(
            workflow,
            cube_alias=cube_alias,
            node_name=image_node_name,
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
                cube_alias=cube_alias,
                image_node_name=image_node_name,
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
                cube_alias=cube_alias,
                image_node_name=image_node_name,
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
            materialized = self._materialize_mask_binding(
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
                cube_alias=binding.cube_alias,
                image_node_name=binding.image_node_name,
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
            cube_alias=cube_alias,
            image_node_name=image_node_name,
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

    def materialize_loaded_cube(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        cube_alias: str,
        workflow_name: str,
        projects_dir: Path,
    ) -> tuple[InputCanvasMaterializationResult, ...]:
        """Load all editable bound input images for one loaded cube into the canvas."""

        started_at = perf_counter()
        workflow = workflows.get(workflow_id)
        if workflow is None:
            return ()
        cube_state = workflow.cubes.get(cube_alias)
        if cube_state is None:
            return ()

        nodes = cube_state.buffer.get("nodes", {})
        if not isinstance(nodes, dict):
            return ()

        results: list[InputCanvasMaterializationResult] = []
        phase_started_at = perf_counter()
        binding_index = self._binding_index_for_cube(workflow, cube_alias)
        image_identities = binding_index.image_identities()
        log_timing(
            _LOGGER,
            "Built editable mask binding index for loaded cube",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_identity_count=len(image_identities),
            level="debug",
        )
        for image_identity in image_identities:
            _, image_node_name = image_identity
            node_data = nodes.get(image_node_name, {})
            if not isinstance(node_data, dict):
                continue
            image_path = node_data.get("inputs", {}).get("image")
            if not isinstance(image_path, str) or not image_path:
                continue
            if not _looks_like_local_path(Path(image_path)):
                log_info(
                    _LOGGER,
                    "Skipped loaded cube input image because it is not a local filesystem path",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    cube_alias=cube_alias,
                    image_node_name=image_node_name,
                    image_path=image_path,
                )
                continue
            result = self.materialize_input_image(
                workflows=workflows,
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                image_node_name=image_node_name,
                image_path=image_path,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
            )
            if result.image_id is not None:
                results.append(result)
        materialized_results = tuple(results)
        log_timing(
            _LOGGER,
            "Materialized loaded cube input canvas bindings",
            started_at=started_at,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            materialization_result_count=len(materialized_results),
            image_identity_count=len(image_identities),
            level="debug",
        )
        return materialized_results

    def _binding_index_for_cube(
        self,
        workflow: WorkflowState,
        cube_alias: str,
    ) -> EditableMaskBindingIndex:
        """Return editable mask binding index for one cube in a workflow."""

        cube_state = workflow.cubes.get(cube_alias)
        if cube_state is None:
            return EditableMaskBindingIndex()
        return self._cube_mask_binding_service.build_index(
            cube_alias,
            cube_state.buffer,
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

    @staticmethod
    def _image_path_from_buffer(
        workflow: WorkflowState,
        cube_alias: str,
        node_name: str,
    ) -> str:
        """Return the current image input path from a workflow graph buffer."""

        cube_state = workflow.cubes.get(cube_alias)
        buffer = cube_state.buffer if cube_state is not None else {}
        nodes = buffer.get("nodes", {}) if isinstance(buffer, dict) else {}
        node = nodes.get(node_name, {}) if isinstance(nodes, dict) else {}
        inputs = node.get("inputs", {}) if isinstance(node, dict) else {}
        value = inputs.get("image") if isinstance(inputs, dict) else None
        return value if isinstance(value, str) else ""

    @staticmethod
    def _parse_input_key(input_key: str) -> tuple[str, str] | None:
        """Parse the durable cube/node input image key."""

        cube_alias, separator, image_node_name = input_key.partition(":")
        if not cube_alias or separator != ":" or not image_node_name:
            return None
        return (cube_alias, image_node_name)

    def _materialize_mask_binding(
        self,
        *,
        workflow: WorkflowState,
        workflow_id: str,
        binding: EditableMaskBinding,
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
                cube_alias=binding.cube_alias,
                image_node_name=binding.image_node_name,
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
                cube_alias=binding.cube_alias,
                image_node_name=binding.image_node_name,
                mask_node_name=binding.mask_node_name,
                input_image_path=str(associated_image_path),
                size_type=type(resolved_size).__name__,
            )
            return None

        cube_state = workflow.cubes.get(binding.cube_alias)
        if cube_state is None:
            return None
        nodes = cube_state.buffer.get("nodes", {})
        if not isinstance(nodes, dict):
            return None
        mask_node = nodes.get(binding.mask_node_name, {})
        if not isinstance(mask_node, dict):
            return None
        mask_inputs = mask_node.get("inputs", {})
        if not isinstance(mask_inputs, dict):
            return None

        raw_mask_path = mask_inputs.get("image")
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
            cube_alias=binding.cube_alias,
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
                cube_alias=binding.cube_alias,
                image_node_name=binding.image_node_name,
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
                    cube_alias=binding.cube_alias,
                    image_node_name=binding.image_node_name,
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
                cube_alias=binding.cube_alias,
                image_node_name=binding.image_node_name,
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
                    cube_alias=binding.cube_alias,
                    image_node_name=binding.image_node_name,
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
                    cube_alias=binding.cube_alias,
                    image_node_name=binding.image_node_name,
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
                    cube_alias=binding.cube_alias,
                    image_node_name=binding.image_node_name,
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
                    cube_alias=binding.cube_alias,
                    image_node_name=binding.image_node_name,
                    mask_node_name=binding.mask_node_name,
                    input_image_path=str(associated_image_path),
                    expected_mask_path=resolved_expected_text,
                    expected_size=image_dimensions,
                    actual_mask_size=mask_dimensions,
                )
            selected_mask_path = self._canvas_io_service.allocate_bound_mask_path(
                workflow_name=workflow_name,
                associated_image_path=associated_image_path,
                cube_alias=binding.cube_alias,
                mask_node_name=binding.mask_node_name,
                image_size=image_dimensions,
                projects_dir=projects_dir,
            )
            log_debug(
                _LOGGER,
                "Creating compatible replacement editable mask",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=binding.cube_alias,
                image_node_name=binding.image_node_name,
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
                cube_alias=binding.cube_alias,
                image_node_name=binding.image_node_name,
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
                    cube_alias=binding.cube_alias,
                    image_node_name=binding.image_node_name,
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
                cube_alias=binding.cube_alias,
                image_node_name=binding.image_node_name,
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
                cube_alias=binding.cube_alias,
                image_node_name=binding.image_node_name,
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
        binding: EditableMaskBinding,
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
                cube_alias=binding.cube_alias,
                image_node_name=binding.image_node_name,
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
            cube_alias=binding.cube_alias,
            image_node_name=binding.image_node_name,
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
        binding: EditableMaskBinding,
        path: Path,
    ) -> None:
        """Store project-mask ownership for one materialized editable mask."""

        relative_path = path.name
        associated = self._workflow_asset_service.associate_project_input_mask(
            workflow,
            cube_alias=binding.cube_alias,
            node_name=binding.mask_node_name,
            relative_path=relative_path,
        )
        log_debug(
            _LOGGER,
            "Associated materialized editable mask with workflow asset state",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=binding.cube_alias,
            image_node_name=binding.image_node_name,
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
        binding: EditableMaskBinding,
        projects_dir: Path,
    ) -> Path | None:
        """Return a durable mask asset path when the mask node has metadata."""

        asset_ref = self._workflow_asset_service.input_mask_asset_ref(
            workflow,
            cube_alias=binding.cube_alias,
            node_name=binding.mask_node_name,
        )
        if asset_ref is None:
            return None
        resolved_path = self._workflow_asset_service.resolve_input_mask_path(
            workflow,
            workflow_name=workflow_name,
            cube_alias=binding.cube_alias,
            node_name=binding.mask_node_name,
            projects_dir=projects_dir,
        )
        log_debug(
            _LOGGER,
            "Resolved explicit editable mask asset path",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=binding.cube_alias,
            image_node_name=binding.image_node_name,
            mask_node_name=binding.mask_node_name,
            asset_ref_kind=getattr(asset_ref, "kind", ""),
            resolved_path=str(resolved_path) if resolved_path is not None else "",
        )
        return resolved_path


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
