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

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from PySide6.QtCore import QTimer

from substitute.application.errors import (
    ErrorReport,
    ErrorReportKind,
    SubstituteOperationContext,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_mask_tool_controller import (
    InputMaskToolController,
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


class _TimerPort(Protocol):
    """Describe static single-shot scheduling used for picker refresh."""

    @staticmethod
    def singleShot(msec: int, callback: Callable[[], None]) -> None:  # noqa: N802
        """Schedule one callback."""


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


class _CanvasTabsPort(Protocol):
    """Describe attached canvas focus behavior."""

    canvas_map: Mapping[str, object]

    def focus_attached_canvas(self, label: str) -> None:
        """Focus one attached canvas tab."""


class _WorkflowInputCanvasServicePort(Protocol):
    """Describe application-owned Input canvas reconciliation."""

    def bindings_for_image(
        self,
        workflow: WorkflowState,
        cube_alias: str,
        image_node_name: str,
    ) -> tuple[object, ...]:
        """Return editable mask bindings attached to one image node."""

    def binding_for_mask(
        self,
        workflow: WorkflowState,
        cube_alias: str,
        mask_node_name: str,
    ) -> object | None:
        """Return the unambiguous binding for one mask node."""

    def resolve_loaded_input_canvas_image_identity(
        self,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> object:
        """Resolve a QPane image id to a workflow graph input identity."""

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
        """Associate one QPane-loaded image with workflow Input state."""

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


class InputCanvasPresenter:
    """Own Input canvas view intent and editor-panel picker refresh policy."""

    def __init__(
        self,
        *,
        input_pane: object,
        current_image_id_provider: Callable[[], UUID | None],
        active_workflow_provider: Callable[[], WorkflowState | None],
        active_editor_panel_provider: Callable[[], _EditorPanelPort | None],
        workflow_session_service: _WorkflowSessionServicePort,
        workflow_input_canvas_service: _WorkflowInputCanvasServicePort,
        input_canvas_state_service: _InputCanvasStateServicePort,
        canvas_tabs_provider: Callable[[], _CanvasTabsPort | None],
        workflow_name_provider: Callable[[str], str],
        projects_dir_provider: Callable[[], Path],
        mask_color_provider: Callable[[int, int], object],
        mask_tool_controller: InputMaskToolController,
        mark_canvas_changed: Callable[[str], None] | None = None,
        error_presenter: ErrorReportPresenterProtocol | None = None,
        timer: type[_TimerPort] | None = None,
    ) -> None:
        """Store presenter collaborators and connect QPane Input signals."""

        self._input_pane = input_pane
        self._current_image_id_provider = current_image_id_provider
        self._active_workflow_provider = active_workflow_provider
        self._active_editor_panel_provider = active_editor_panel_provider
        self._workflow_session_service = workflow_session_service
        self._workflow_input_canvas_service = workflow_input_canvas_service
        self._input_canvas_state_service = input_canvas_state_service
        self._canvas_tabs_provider = canvas_tabs_provider
        self._workflow_name_provider = workflow_name_provider
        self._projects_dir_provider = projects_dir_provider
        self._mask_color_provider = mask_color_provider
        self._mask_tool_controller = mask_tool_controller
        self._mark_canvas_changed = mark_canvas_changed
        self._error_presenter = error_presenter
        self._timer = timer or cast(type[_TimerPort], QTimer)
        self._bind_qpane_signals()

    def handle_input_image_changed(
        self,
        cube_alias: str,
        node_name: str,
        image_path: str,
    ) -> None:
        """Materialize one editor-panel LoadImage selection."""

        active_workflow = self._active_workflow_provider()
        if active_workflow is None or not image_path:
            return
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
        self.apply_materialization_result(result, projects_dir=projects_dir)
        self._mark_changed(workflow_id)

    def handle_input_canvas_image_loaded(
        self,
        image_id: object,
        image_path: str,
    ) -> None:
        """Associate one QPane-loaded Input image with workflow graph state."""

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
        self.apply_materialization_result(result, projects_dir=projects_dir)
        self._mark_changed(workflow_id)

    def handle_input_image_clicked(
        self,
        cube_alias: str,
        node_name: str,
        _image_path: str,
    ) -> None:
        """Focus the Input canvas image and first bound mask for a picker click."""

        active_workflow = self._active_workflow_provider()
        if active_workflow is None:
            return
        workflow_id = self._workflow_session_service.active_workflow_id
        input_key = f"{cube_alias}:{node_name}"
        canvas = getattr(active_workflow, "canvas", None)
        input_key_map = getattr(canvas, "input_key_map", {})
        image_uuid = (
            input_key_map.get(input_key) if isinstance(input_key_map, Mapping) else None
        )
        if not isinstance(image_uuid, UUID):
            return
        if not self._input_canvas_state_service.set_active_input_image(
            workflow_id,
            active_workflow,
            image_uuid,
        ):
            return
        self._focus_attached_canvas("Input")
        bindings = self._workflow_input_canvas_service.bindings_for_image(
            active_workflow,
            cube_alias,
            node_name,
        )
        if bindings:
            first_binding = bindings[0]
            association_key = getattr(first_binding, "association_key", None)
            mask_associations = getattr(canvas, "mask_associations", {})
            mask_id = (
                mask_associations.get(association_key)
                if isinstance(mask_associations, Mapping)
                else None
            )
            if isinstance(mask_id, UUID):
                self._set_active_workflow_mask(active_workflow, mask_id)
        self._timer.singleShot(0, self.refresh_active_mask_pickers)

    def handle_input_mask_changed(
        self,
        cube_alias: str,
        node_name: str,
        mask_path: str,
    ) -> None:
        """Apply one user-selected LoadImageMask file and refresh from asset state."""

        active_workflow = self._active_workflow_provider()
        if active_workflow is None or not mask_path:
            return
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
            return
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
                return
            self._report_wrong_size_input_mask(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_path=mask_path,
                selected_dimensions=selected_dimensions,
                required_dimensions=required_dimensions,
            )
            return
        if not bool(getattr(result, "applied", False)):
            return
        materialization_result = getattr(result, "materialization_result", None)
        if materialization_result is not None:
            self.apply_materialization_result(
                materialization_result,
                projects_dir=projects_dir,
            )
        self.refresh_mask_picker_from_asset_state(
            cube_alias,
            node_name,
            projects_dir=projects_dir,
        )
        self._mark_changed(workflow_id)

    def handle_input_mask_clicked(
        self,
        cube_alias: str,
        node_name: str,
        _mask_path: str,
    ) -> None:
        """Activate the owning image and mask, then request brush mode."""

        active_workflow = self._active_workflow_provider()
        if active_workflow is None:
            return
        workflow_id = self._workflow_session_service.active_workflow_id
        binding = self._workflow_input_canvas_service.binding_for_mask(
            active_workflow,
            cube_alias,
            node_name,
        )
        if binding is None:
            log_warning(
                _LOGGER,
                "Rejected input mask click without graph binding",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                node_name=node_name,
                rejection_reason="missing_mask_binding",
            )
            return
        binding_cube_alias = getattr(binding, "cube_alias", None)
        image_node_name = getattr(binding, "image_node_name", None)
        association_key = getattr(binding, "association_key", None)
        if not isinstance(binding_cube_alias, str) or not isinstance(
            image_node_name, str
        ):
            return
        input_key = f"{binding_cube_alias}:{image_node_name}"
        canvas = getattr(active_workflow, "canvas", None)
        input_key_map = getattr(canvas, "input_key_map", {})
        image_uuid = (
            input_key_map.get(input_key) if isinstance(input_key_map, Mapping) else None
        )
        if not isinstance(image_uuid, UUID):
            log_warning(
                _LOGGER,
                "Rejected input mask click without materialized owning image",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                node_name=node_name,
                input_key=input_key,
                rejection_reason="missing_bound_input_image",
            )
            return
        if not self._input_canvas_state_service.set_active_input_image(
            workflow_id,
            active_workflow,
            image_uuid,
        ):
            return
        mask_associations = getattr(canvas, "mask_associations", {})
        mask_id = (
            mask_associations.get(association_key)
            if isinstance(mask_associations, Mapping)
            else None
        )
        if not isinstance(mask_id, UUID):
            log_warning(
                _LOGGER,
                "Rejected input mask click without associated canvas mask",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                node_name=node_name,
                association_key=association_key,
                rejection_reason="missing_canvas_mask",
            )
            return
        if not self._set_active_workflow_mask(active_workflow, mask_id):
            return
        self._focus_attached_canvas("Input")
        self._mask_tool_controller.request_brush_mode_after_authorized_mask_activation()

    def handle_mask_save_completed(self, mask_id: object, path: str = "") -> None:
        """Refresh a saved mask picker from current asset state, not emitted path."""

        active_workflow = self._active_workflow_provider()
        active_panel = self._active_editor_panel_provider()
        if active_workflow is None or active_panel is None:
            return
        resolved_mask_id = self._resolve_uuid(mask_id)
        if resolved_mask_id is None:
            return
        association_key = self._association_key_for_mask(
            active_workflow,
            resolved_mask_id,
        )
        if association_key is None:
            log_debug(
                _LOGGER,
                "Ignoring mask save completion for unassociated mask id",
                workflow_id=self._workflow_session_service.active_workflow_id,
                mask_id=str(mask_id),
                emitted_path=path,
            )
            return
        cube_alias, node_name = association_key

        def refresh_after_save() -> None:
            """Refresh after Qt returns to the event loop."""

            self.refresh_mask_picker_from_asset_state(cube_alias, node_name)

        self._timer.singleShot(0, refresh_after_save)

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
            self.apply_materialization_result(result, projects_dir=projects_dir)
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
        """Associate the active QPane image with workflow Input graph state."""

        current_image_path = getattr(self._input_pane, "currentImagePath", None)
        image_path = (
            current_image_path() if callable(current_image_path) else current_image_path
        )
        image_id = self._current_image_id_provider()
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

    def apply_materialization_result(
        self,
        result: object,
        *,
        projects_dir: Path | None = None,
    ) -> None:
        """Apply Input materialization presentation effects without path authority."""

        input_pane = self._input_pane
        raw_mask_results = getattr(result, "mask_results", ())
        mask_results = (
            tuple(raw_mask_results) if isinstance(raw_mask_results, Iterable) else ()
        )
        total_masks_in_set = len(mask_results)
        for index, mask_result in enumerate(mask_results):
            set_mask_properties = getattr(input_pane, "setMaskProperties", None)
            mask_id = getattr(mask_result, "mask_id", None)
            if callable(set_mask_properties) and isinstance(mask_id, UUID):
                color = self._mask_color_provider(index, total_masks_in_set)
                set_mask_properties(mask_id, color=color)
            association_key = getattr(mask_result, "association_key", None)
            if self._valid_association_key(association_key):
                cube_alias, node_name = cast(tuple[str, str], association_key)
                self.refresh_mask_picker_from_asset_state(
                    cube_alias,
                    node_name,
                    projects_dir=projects_dir,
                )
        first_mask_id = getattr(result, "first_mask_id", None)
        active_workflow = self._active_workflow_provider()
        if isinstance(first_mask_id, UUID) and active_workflow is not None:
            self._set_active_workflow_mask(active_workflow, first_mask_id)

    def refresh_active_mask_pickers(self) -> None:
        """Refresh active editor mask pickers from workflow asset state."""

        active_workflow = self._active_workflow_provider()
        if active_workflow is None or self._active_editor_panel_provider() is None:
            return
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

    def _bind_qpane_signals(self) -> None:
        """Connect QPane image and mask events to presenter-owned handlers."""

        mask_saved = getattr(self._input_pane, "maskSaved", None)
        connect_mask_saved = getattr(mask_saved, "connect", None)
        if callable(connect_mask_saved):
            connect_mask_saved(self.handle_mask_save_completed)
        image_loaded = getattr(self._input_pane, "imageLoaded", None)
        connect_image_loaded = getattr(image_loaded, "connect", None)
        if callable(connect_image_loaded):
            connect_image_loaded(self._handle_qpane_image_loaded)

    def _handle_qpane_image_loaded(self, path: object) -> None:
        """Handle QPane imageLoaded using the route-authorized image id."""

        image_path = str(path) if path is not None else ""
        self.handle_input_canvas_image_loaded(
            self._current_image_id_provider(),
            image_path,
        )

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

    def _focus_attached_canvas(self, label: str) -> None:
        """Route attached canvas focus and persist the workflow route hint."""

        active_workflow = self._active_workflow_provider()
        canvas = getattr(active_workflow, "canvas", None)
        if canvas is not None and label in {"Input", "Output"}:
            canvas.active_canvas_route = label
        canvas_tabs = self._canvas_tabs_provider()
        focus_attached_canvas = getattr(canvas_tabs, "focus_attached_canvas", None)
        if callable(focus_attached_canvas):
            focus_attached_canvas(label)

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

        associations = getattr(
            getattr(workflow, "canvas", None), "mask_associations", {}
        )
        if not isinstance(associations, Mapping):
            return None
        for key, value in associations.items():
            if InputCanvasPresenter._resolve_uuid(value) == mask_id:
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
        """Resolve UUIDs from QPane or workflow payloads."""

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
