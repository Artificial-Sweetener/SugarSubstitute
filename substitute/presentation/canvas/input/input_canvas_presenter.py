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

"""Coordinate Input canvas intent and authoritative mask picker refresh."""

from __future__ import annotations

from sugarsubstitute_shared.localization import opaque_text

from sugarsubstitute_shared.presentation.localization import app_text

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from substitute.application.errors import (
    ErrorReport,
    ErrorReportKind,
    SubstituteOperationContext,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_node_preview_coordinator import (
    InputNodePreviewCoordinator,
)
from substitute.presentation.canvas.input.input_materialization_presenter import (
    InputMaterializationPresenter,
)
from substitute.presentation.regional.mask_collection_presenter import (
    RegionalMaskCollectionPresenter,
)
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_warning,
)

_LOGGER = get_logger("presentation.canvas.input.input_canvas_presenter")


class _SignalPort(Protocol):
    """Describe a Qt-like signal used by presenter-owned wiring."""

    def connect(self, callback: Callable[..., object]) -> object:
        """Connect one callback to this signal."""


class _WorkflowSessionServicePort(Protocol):
    """Describe active workflow state consumed by Input presentation."""

    active_workflow_id: str
    workflows: Mapping[str, WorkflowState]


class _EditorPanelPort(Protocol):
    """Describe the editor-panel mask picker refresh API."""

    def refresh_mask_picker(
        self, cube_alias: str, node_name: str, new_path: str
    ) -> None:
        """Refresh one editor-panel mask picker preview."""


class _WorkflowInputCanvasServicePort(Protocol):
    """Describe application-owned Input canvas reconciliation."""

    def resolve_loaded_input_canvas_image_identity(
        self,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> object:
        """Resolve a CuteCanvas image id to a workflow graph input identity."""

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
    ) -> object:
        """Materialize one input image and its editable masks."""

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
    ) -> object:
        """Associate one CuteCanvas-loaded image with workflow Input state."""

    def materialize_loaded_section(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        section_key: str,
        workflow_name: str,
        projects_dir: Path,
    ) -> tuple[object, ...]:
        """Materialize editable Input images for one graph section."""

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
    ) -> object:
        """Validate and apply one user-selected Input mask."""

    def resolve_input_mask_path(
        self,
        workflow: WorkflowState,
        *,
        workflow_name: str,
        section_key: str,
        node_name: str,
        projects_dir: Path,
    ) -> Path | None:
        """Resolve one mask path through semantic upload binding ownership."""


class _InputCanvasStateServicePort(Protocol):
    """Describe Input state mutations needed by presenter intent."""

    def set_active_workflow_mask(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        mask_id: UUID,
    ) -> bool:
        """Activate one workflow-owned Input mask."""

    def set_active_input_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> bool:
        """Activate one workflow-owned Input image."""

    def input_image_path(self, image_id: UUID) -> Path | None:
        """Return the persisted path associated with one Input image."""


class InputCanvasPresenter:
    """Own Input canvas view intent and editor-panel picker refresh policy."""

    def __init__(
        self,
        *,
        input_document: object,
        current_image_id_provider: Callable[[], UUID | None],
        active_workflow_provider: Callable[[], WorkflowState | None],
        active_editor_panel_provider: Callable[[], _EditorPanelPort | None],
        workflow_session_service: _WorkflowSessionServicePort,
        workflow_input_canvas_service: _WorkflowInputCanvasServicePort,
        input_canvas_state_service: _InputCanvasStateServicePort,
        workflow_name_provider: Callable[[str], str],
        projects_dir_provider: Callable[[], Path],
        mask_color_provider: Callable[[int, int], object],
        regional_mask_presenter: RegionalMaskCollectionPresenter,
        preview_coordinator: InputNodePreviewCoordinator | None = None,
        mark_canvas_changed: Callable[[str], None] | None = None,
        error_presenter: ErrorReportPresenterProtocol | None = None,
    ) -> None:
        """Store presenter collaborators for Input document presentation."""

        self._input_document = input_document
        self._current_image_id_provider = current_image_id_provider
        self._active_workflow_provider = active_workflow_provider
        self._active_editor_panel_provider = active_editor_panel_provider
        self._workflow_session_service = workflow_session_service
        self._workflow_input_canvas_service = workflow_input_canvas_service
        self._input_canvas_state_service = input_canvas_state_service
        self._workflow_name_provider = workflow_name_provider
        self._projects_dir_provider = projects_dir_provider
        self._preview_coordinator = preview_coordinator
        self._mark_canvas_changed = mark_canvas_changed
        self._error_presenter = error_presenter
        self._materialization_presenter = InputMaterializationPresenter(
            input_document=input_document,
            active_workflow=active_workflow_provider,
            mask_color=mask_color_provider,
            refresh_scalar_mask=lambda cube_alias, node_name, projects_dir: (
                self.refresh_mask_picker_from_asset_state(
                    cube_alias,
                    node_name,
                    projects_dir=projects_dir,
                )
            ),
            refresh_ordered_mask=regional_mask_presenter.refresh,
            activate_mask=self._set_active_workflow_mask,
            preview_coordinator=preview_coordinator,
        )

    def materialize_image_selection(
        self,
        cube_alias: str,
        node_name: str,
        image_path: str,
    ) -> bool:
        """Materialize one editor-panel LoadImage selection and report acceptance."""

        active_workflow = self._active_workflow_provider()
        if active_workflow is None or not image_path:
            return False
        workflow_id = self._workflow_session_service.active_workflow_id
        projects_dir = self._projects_dir_provider()
        result = self._workflow_input_canvas_service.materialize_input_image(
            workflows=self._workflow_session_service.workflows,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_node_name=node_name,
            image_path=image_path,
            workflow_name=self._workflow_name_provider(workflow_id),
            projects_dir=projects_dir,
        )
        self._materialization_presenter.apply(result, projects_dir=projects_dir)
        self._mark_changed(workflow_id)
        return isinstance(getattr(result, "image_id", None), UUID)

    def handle_input_canvas_image_loaded(
        self,
        image_id: object,
        image_path: str,
    ) -> None:
        """Associate one CuteCanvas-admitted Input image with workflow graph state."""

        active_workflow = self._active_workflow_provider()
        workflow_id = self._workflow_session_service.active_workflow_id
        resolved_image_id = self._resolve_uuid(image_id)
        if active_workflow is None or resolved_image_id is None or not image_path:
            return
        identity = self._workflow_input_canvas_service.resolve_loaded_input_canvas_image_identity(
            active_workflow,
            resolved_image_id,
        )
        if not bool(getattr(identity, "accepted", False)):
            log_warning(
                _LOGGER,
                "Skipping input canvas image association for unresolved graph identity",
                workflow_id=workflow_id,
                image_id=str(resolved_image_id),
                image_path=image_path,
                input_key=getattr(identity, "input_key", None),
                skip_reason=getattr(identity, "rejection_reason", None)
                or "unmapped_image_id",
            )
            return
        cube_alias = getattr(identity, "cube_alias", None)
        node_name = getattr(identity, "image_node_name", None)
        if not isinstance(cube_alias, str) or not isinstance(node_name, str):
            return
        projects_dir = self._projects_dir_provider()
        result = (
            self._workflow_input_canvas_service.reconcile_loaded_input_canvas_image(
                workflows=self._workflow_session_service.workflows,
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                image_node_name=node_name,
                image_id=resolved_image_id,
                image_path=image_path,
                workflow_name=self._workflow_name_provider(workflow_id),
                projects_dir=projects_dir,
            )
        )
        self._materialization_presenter.apply(result, projects_dir=projects_dir)
        self._mark_changed(workflow_id)

    def apply_mask_selection(
        self,
        cube_alias: str,
        node_name: str,
        mask_path: str,
    ) -> bool:
        """Apply one selected LoadImageMask file and report acceptance."""

        active_workflow = self._active_workflow_provider()
        if active_workflow is None or not mask_path:
            return False
        workflow_id = self._workflow_session_service.active_workflow_id
        workflow_name = self._workflow_name_provider(workflow_id)
        projects_dir = self._projects_dir_provider()
        result = self._workflow_input_canvas_service.apply_user_selected_input_mask(
            workflows=self._workflow_session_service.workflows,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            mask_node_name=node_name,
            mask_path=mask_path,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
        )
        rejection_reason = getattr(result, "rejection_reason", "")
        if rejection_reason == "unverified_dimensions":
            self._report_unverified_input_mask_dimensions(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_path=mask_path,
                selected_dimensions=getattr(result, "selected_dimensions", None),
                required_dimensions=getattr(result, "required_dimensions", None),
            )
            return False
        if rejection_reason == "dimension_mismatch":
            selected_dimensions = getattr(result, "selected_dimensions", None)
            required_dimensions = getattr(result, "required_dimensions", None)
            if selected_dimensions is None or required_dimensions is None:
                self._report_unverified_input_mask_dimensions(
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    cube_alias=cube_alias,
                    node_name=node_name,
                    mask_path=mask_path,
                    selected_dimensions=selected_dimensions,
                    required_dimensions=required_dimensions,
                )
                return False
            self._report_wrong_size_input_mask(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_path=mask_path,
                selected_dimensions=selected_dimensions,
                required_dimensions=required_dimensions,
            )
            return False
        if not bool(getattr(result, "applied", False)):
            return False
        materialization_result = getattr(result, "materialization_result", None)
        if materialization_result is not None:
            self._materialization_presenter.apply(
                materialization_result,
                projects_dir=projects_dir,
            )
        self.refresh_mask_picker_from_asset_state(
            cube_alias,
            node_name,
            projects_dir=projects_dir,
        )
        self._mark_changed(workflow_id)
        return True

    def materialize_loaded_cube_input_canvas(
        self,
        workflow_id: str,
        cube_alias: str,
    ) -> None:
        """Materialize editable Input images and masks for one loaded cube."""

        if workflow_id != self._workflow_session_service.active_workflow_id:
            log_warning(
                _LOGGER,
                "Skipped loaded cube input-canvas materialization because workflow was inactive",
                workflow_id=workflow_id,
                active_workflow_id=self._workflow_session_service.active_workflow_id,
                cube_alias=cube_alias,
            )
            return
        self.materialize_loaded_workflow_section(workflow_id, cube_alias)

    def materialize_loaded_workflow_section(
        self,
        workflow_id: str,
        section_key: str,
    ) -> None:
        """Materialize local upload endpoints for one active graph section."""

        if workflow_id != self._workflow_session_service.active_workflow_id:
            return
        projects_dir = self._projects_dir_provider()
        results = self._workflow_input_canvas_service.materialize_loaded_section(
            workflows=self._workflow_session_service.workflows,
            workflow_id=workflow_id,
            section_key=section_key,
            workflow_name=self._workflow_name_provider(workflow_id),
            projects_dir=projects_dir,
        )
        for result in results:
            self._materialization_presenter.apply(result, projects_dir=projects_dir)
        self.bind_active_node_previews()
        if results:
            self._mark_changed(workflow_id)
        log_info(
            _LOGGER,
            "Completed loaded graph-section input-canvas materialization",
            workflow_id=workflow_id,
            section_key=section_key,
            materialization_result_count=len(results),
        )

    def reconcile_active_input_canvas_image(self) -> None:
        """Associate the active document image with workflow Input graph state."""

        image_id = self._current_image_id_provider()
        image_path = (
            self._input_canvas_state_service.input_image_path(image_id)
            if image_id is not None
            else None
        )
        log_debug(
            _LOGGER,
            "Reconciling active input canvas image through presenter",
            workflow_id=self._workflow_session_service.active_workflow_id,
            image_id=str(image_id),
            image_path=str(image_path) if image_path is not None else "",
        )
        self.handle_input_canvas_image_loaded(
            image_id,
            str(image_path) if image_path is not None else "",
        )

    def refresh_active_mask_pickers(self) -> None:
        """Refresh active editor mask pickers from workflow asset state."""

        active_workflow = self._active_workflow_provider()
        if active_workflow is None or self._active_editor_panel_provider() is None:
            return
        self.bind_active_node_previews()
        cubes = getattr(active_workflow, "cubes", {})
        if not isinstance(cubes, Mapping):
            return
        projects_dir = self._projects_dir_provider()
        for cube_alias, cube_state in cubes.items():
            if not isinstance(cube_alias, str):
                continue
            buffer = getattr(cube_state, "buffer", {})
            nodes = buffer.get("nodes", {}) if isinstance(buffer, Mapping) else {}
            if not isinstance(nodes, Mapping):
                continue
            for node_name, node_data in nodes.items():
                if not isinstance(node_name, str) or not isinstance(node_data, Mapping):
                    continue
                if node_data.get("class_type") != "LoadImageMask":
                    continue
                self.refresh_mask_picker_from_asset_state(
                    cube_alias,
                    node_name,
                    projects_dir=projects_dir,
                )

    def bind_active_node_previews(self) -> frozenset[tuple[str, str]]:
        """Bind current panel previews from authoritative active workflow state."""
        active_workflow = self._active_workflow_provider()
        if active_workflow is None or self._preview_coordinator is None:
            return frozenset()
        return self._preview_coordinator.bind_workflow(active_workflow)

    def refresh_mask_picker_from_asset_state(
        self,
        cube_alias: str,
        node_name: str,
        *,
        projects_dir: Path | None = None,
    ) -> bool:
        """Refresh one editor-panel picker from authoritative workflow asset state."""

        active_workflow = self._active_workflow_provider()
        active_panel = self._active_editor_panel_provider()
        if active_workflow is None or active_panel is None:
            return False
        if (
            self._preview_coordinator is not None
            and self._preview_coordinator.mask_preview_mounted(
                cube_alias,
                node_name,
            )
        ):
            return True
        workflow_id = self._workflow_session_service.active_workflow_id
        resolved_projects_dir = projects_dir or self._projects_dir_provider()
        resolved_path = self._workflow_input_canvas_service.resolve_input_mask_path(
            active_workflow,
            workflow_name=self._workflow_name_provider(workflow_id),
            section_key=cube_alias,
            node_name=node_name,
            projects_dir=resolved_projects_dir,
        )
        if resolved_path is None or not resolved_path.exists():
            return False
        active_panel.refresh_mask_picker(cube_alias, node_name, str(resolved_path))
        log_debug(
            _LOGGER,
            "Refreshed mask picker from workflow asset state",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            node_name=node_name,
            resolved_path=str(resolved_path),
        )
        return True

    def _set_active_workflow_mask(
        self,
        active_workflow: WorkflowState,
        mask_id: UUID,
    ) -> bool:
        """Activate one workflow mask through InputCanvasStateService."""

        return self._input_canvas_state_service.set_active_workflow_mask(
            self._workflow_session_service.active_workflow_id,
            active_workflow,
            mask_id,
        )

    def _mark_changed(self, workflow_id: str) -> None:
        """Notify shell-owned surface invalidation when configured."""

        if self._mark_canvas_changed is not None:
            self._mark_canvas_changed(workflow_id)

    @staticmethod
    def _association_key_for_mask(
        workflow: object,
        mask_id: UUID,
    ) -> tuple[str, str] | None:
        """Return the associated cube/mask node for one runtime mask id."""

        canvas = getattr(workflow, "canvas", None)
        mask_entries = getattr(canvas, "mask_entries", {})
        if not isinstance(mask_entries, Mapping):
            return None
        for key, entry in mask_entries.items():
            if (
                InputCanvasPresenter._resolve_uuid(getattr(entry, "mask_id", None))
                == mask_id
            ):
                return (
                    cast(tuple[str, str], key)
                    if InputCanvasPresenter._valid_association_key(key)
                    else None
                )
        return None

    @staticmethod
    def _valid_association_key(value: object) -> bool:
        """Return whether value is a concrete cube/mask node association key."""

        return (
            isinstance(value, tuple)
            and len(value) == 2
            and isinstance(value[0], str)
            and isinstance(value[1], str)
        )

    @staticmethod
    def _resolve_uuid(value: object) -> UUID | None:
        """Resolve UUIDs from CuteCanvas or workflow payloads."""

        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            try:
                return UUID(value)
            except ValueError:
                return None
        return None

    def _report_wrong_size_input_mask(
        self,
        *,
        workflow_id: str,
        workflow_name: str,
        cube_alias: str,
        node_name: str,
        mask_path: str,
        selected_dimensions: tuple[int, int],
        required_dimensions: tuple[int, int],
    ) -> None:
        """Report a selected mask whose dimensions do not match the input image."""

        log_warning(
            _LOGGER,
            "Rejected user-selected input mask with wrong dimensions",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            node_name=node_name,
            mask_path=mask_path,
            selected_mask_size=selected_dimensions,
            required_image_size=required_dimensions,
        )
        if self._error_presenter is None:
            return
        self._error_presenter.show_error_report(
            ErrorReport(
                kind=ErrorReportKind.SUBSTITUTE_INTERNAL,
                title=app_text("Mask dimensions do not match"),
                message=(
                    app_text(
                        "The selected mask dimensions do not match the loaded input image."
                    )
                ),
                stage="input_mask",
                workflow_id=workflow_id,
                technical_detail=(
                    f"Selected mask: {selected_dimensions[0]}x{selected_dimensions[1]}\n"
                    f"Required image: {required_dimensions[0]}x{required_dimensions[1]}\n"
                    f"Cube: {cube_alias}\n"
                    f"Mask node: {node_name}\n"
                    f"Path: {mask_path}"
                ),
                operation_context=SubstituteOperationContext(
                    operation="load_input_mask",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    path=mask_path,
                    node_name=node_name,
                    cube_alias=cube_alias,
                    values={
                        "selected_mask_width": selected_dimensions[0],
                        "selected_mask_height": selected_dimensions[1],
                        "required_image_width": required_dimensions[0],
                        "required_image_height": required_dimensions[1],
                    },
                ),
            )
        )

    def _report_unverified_input_mask_dimensions(
        self,
        *,
        workflow_id: str,
        workflow_name: str,
        cube_alias: str,
        node_name: str,
        mask_path: str,
        selected_dimensions: tuple[int, int] | None,
        required_dimensions: tuple[int, int] | None,
    ) -> None:
        """Report a selected mask whose dimensions cannot be verified."""

        log_warning(
            _LOGGER,
            "Rejected user-selected input mask with unverified dimensions",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            node_name=node_name,
            mask_path=mask_path,
            selected_mask_size=selected_dimensions,
            required_image_size=required_dimensions,
        )
        if self._error_presenter is None:
            return
        selected_text = self._dimensions_text(selected_dimensions)
        required_text = self._dimensions_text(required_dimensions)
        self._error_presenter.show_error_report(
            ErrorReport(
                kind=ErrorReportKind.SUBSTITUTE_INTERNAL,
                title=app_text("Mask dimensions could not be verified"),
                message=(
                    app_text(
                        "The selected mask dimensions could not be verified against "
                        "the loaded input image."
                    )
                ),
                stage="input_mask",
                workflow_id=workflow_id,
                technical_detail=(
                    f"Selected mask: {selected_text}\n"
                    f"Required image: {required_text}\n"
                    f"Cube: {cube_alias}\n"
                    f"Mask node: {node_name}\n"
                    f"Path: {mask_path}"
                ),
                operation_context=SubstituteOperationContext(
                    operation="load_input_mask",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    path=mask_path,
                    node_name=node_name,
                    cube_alias=cube_alias,
                    values={
                        "selected_mask_size": selected_text,
                        "required_image_size": required_text,
                    },
                ),
            )
        )

    @staticmethod
    def _dimensions_text(dimensions: tuple[int, int] | None) -> str:
        """Return display text for optional dimensions."""

        if dimensions is None:
            return opaque_text("unavailable")
        return f"{dimensions[0]}x{dimensions[1]}"


__all__ = ["InputCanvasPresenter"]
