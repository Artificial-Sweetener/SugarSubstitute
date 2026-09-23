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

"""Present Input image selection, admission, and loaded-section materialization."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_materialization_presenter import (
    InputMaterializationPresenter,
)
from substitute.presentation.canvas.input.input_node_preview_coordinator import (
    InputNodePreviewCoordinator,
)
from substitute.presentation.canvas.input.input_presentation_ports import (
    EditorMaskPickerPort,
    InputCanvasBindingPort,
    InputImageStatePort,
    InputImageWorkflowPort,
    InputSectionMaterializationPort,
    WorkflowSessionPort,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_warning,
)

_LOGGER = get_logger("presentation.canvas.input.input_image_materialization_presenter")


class InputImageMaterializationPresenter:
    """Own Input image intent and loaded graph-section presentation."""

    def __init__(
        self,
        *,
        current_image_id: Callable[[], UUID | None],
        active_workflow: Callable[[], WorkflowState | None],
        active_panel: Callable[[], EditorMaskPickerPort | None],
        workflow_session: WorkflowSessionPort,
        workflow_inputs: InputImageWorkflowPort,
        section_materialization: InputSectionMaterializationPort,
        input_bindings: InputCanvasBindingPort,
        input_state: InputImageStatePort,
        workflow_name: Callable[[str], str],
        projects_dir: Callable[[], Path],
        materialization: InputMaterializationPresenter,
        preview_coordinator: InputNodePreviewCoordinator | None = None,
        mark_changed: Callable[[str], None] | None = None,
    ) -> None:
        """Store image workflow, document projection, and invalidation owners."""

        self._current_image_id = current_image_id
        self._active_workflow = active_workflow
        self._active_panel = active_panel
        self._workflow_session = workflow_session
        self._workflow_inputs = workflow_inputs
        self._section_materialization = section_materialization
        self._input_bindings = input_bindings
        self._input_state = input_state
        self._workflow_name = workflow_name
        self._projects_dir = projects_dir
        self._materialization = materialization
        self._preview_coordinator = preview_coordinator
        self._mark_changed = mark_changed

    def materialize_selection(
        self,
        cube_alias: str,
        node_name: str,
        image_path: str,
    ) -> bool:
        """Materialize one editor-panel image selection and report acceptance."""

        if self._active_workflow() is None or not image_path:
            return False
        workflow_id = self._workflow_session.active_workflow_id
        projects_dir = self._projects_dir()
        result = self._workflow_inputs.materialize_input_image(
            workflows=self._workflow_session.workflows,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_node_name=node_name,
            image_path=image_path,
            workflow_name=self._workflow_name(workflow_id),
            projects_dir=projects_dir,
        )
        self._materialization.apply(result, projects_dir=projects_dir)
        self._notify_changed(workflow_id)
        return isinstance(getattr(result, "image_id", None), UUID)

    def handle_loaded_image(self, image_id: object, image_path: str) -> None:
        """Associate one canvas-admitted image with workflow graph state."""

        workflow = self._active_workflow()
        workflow_id = self._workflow_session.active_workflow_id
        resolved_image_id = _resolve_uuid(image_id)
        if workflow is None or resolved_image_id is None or not image_path:
            return
        identity = self._input_bindings.resolve_loaded_image_identity(
            workflow,
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
        projects_dir = self._projects_dir()
        result = self._workflow_inputs.reconcile_loaded_input_canvas_image(
            workflows=self._workflow_session.workflows,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            image_node_name=node_name,
            image_id=resolved_image_id,
            image_path=image_path,
            workflow_name=self._workflow_name(workflow_id),
            projects_dir=projects_dir,
        )
        self._materialization.apply(result, projects_dir=projects_dir)
        self._notify_changed(workflow_id)

    def materialize_loaded_cube(self, workflow_id: str, cube_alias: str) -> None:
        """Materialize editable Input assets for one loaded cube."""

        if workflow_id != self._workflow_session.active_workflow_id:
            log_warning(
                _LOGGER,
                "Skipped loaded cube input-canvas materialization because workflow was inactive",
                workflow_id=workflow_id,
                active_workflow_id=self._workflow_session.active_workflow_id,
                cube_alias=cube_alias,
            )
            return
        self.materialize_loaded_section(workflow_id, cube_alias)

    def materialize_loaded_section(
        self,
        workflow_id: str,
        section_key: str,
    ) -> None:
        """Materialize local upload endpoints for one active graph section."""

        if workflow_id != self._workflow_session.active_workflow_id:
            return
        projects_dir = self._projects_dir()
        results = self._section_materialization.materialize_loaded_section(
            workflows=self._workflow_session.workflows,
            workflow_id=workflow_id,
            section_key=section_key,
            workflow_name=self._workflow_name(workflow_id),
            projects_dir=projects_dir,
        )
        for result in results:
            self._materialization.apply(result, projects_dir=projects_dir)
        if self._preview_coordinator is not None:
            self._preview_coordinator.bind_panel(self._active_panel())
        if results:
            self._notify_changed(workflow_id)
        log_info(
            _LOGGER,
            "Completed loaded graph-section input-canvas materialization",
            workflow_id=workflow_id,
            section_key=section_key,
            materialization_result_count=len(results),
        )

    def reconcile_active(self) -> None:
        """Associate the active document image with workflow Input graph state."""

        image_id = self._current_image_id()
        image_path = (
            self._input_state.path_for(image_id) if image_id is not None else None
        )
        log_debug(
            _LOGGER,
            "Reconciling active input canvas image through presenter",
            workflow_id=self._workflow_session.active_workflow_id,
            image_id=str(image_id),
            image_path=str(image_path) if image_path is not None else "",
        )
        self.handle_loaded_image(
            image_id,
            str(image_path) if image_path is not None else "",
        )

    def _notify_changed(self, workflow_id: str) -> None:
        """Notify shell-owned surface invalidation when configured."""

        if self._mark_changed is not None:
            self._mark_changed(workflow_id)


def _resolve_uuid(value: object) -> UUID | None:
    """Resolve UUIDs from canvas or workflow payloads."""

    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


__all__ = ["InputImageMaterializationPresenter"]
