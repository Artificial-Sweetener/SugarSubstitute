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

"""Project authoritative workflow mask assets into editor-panel pickers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from substitute.application.workflows.input_asset_picker_refresh_service import (
    scalar_mask_picker_identities,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_node_preview_coordinator import (
    InputNodePreviewCoordinator,
)
from substitute.presentation.canvas.input.input_presentation_ports import (
    EditorMaskPickerPort,
    InputCanvasBindingPort,
    InputMaskPickerWorkflowPort,
    WorkflowSessionPort,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.canvas.input.input_mask_picker_presenter")


class InputMaskPickerPresenter:
    """Own scalar mask-picker refresh from authoritative workflow assets."""

    def __init__(
        self,
        *,
        active_workflow: Callable[[], WorkflowState | None],
        active_panel: Callable[[], EditorMaskPickerPort | None],
        workflow_session: WorkflowSessionPort,
        input_bindings: InputCanvasBindingPort,
        workflow_inputs: InputMaskPickerWorkflowPort,
        workflow_name: Callable[[str], str],
        projects_dir: Callable[[], Path],
        preview_coordinator: InputNodePreviewCoordinator | None = None,
    ) -> None:
        """Store workflow asset and mounted editor projection collaborators."""

        self._active_workflow = active_workflow
        self._active_panel = active_panel
        self._workflow_session = workflow_session
        self._input_bindings = input_bindings
        self._workflow_inputs = workflow_inputs
        self._workflow_name = workflow_name
        self._projects_dir = projects_dir
        self._preview_coordinator = preview_coordinator

    def refresh_active(self) -> None:
        """Refresh every scalar mask picker mounted for the active workflow."""

        workflow = self._active_workflow()
        panel = self._active_panel()
        if workflow is None or panel is None:
            return
        if self._preview_coordinator is not None:
            self._preview_coordinator.bind_panel(panel)
        projects_dir = self._projects_dir()
        for cube_alias, node_name in scalar_mask_picker_identities(
            workflow,
            self._input_bindings.plan,
        ):
            self.refresh(
                cube_alias,
                node_name,
                projects_dir=projects_dir,
            )

    def refresh(
        self,
        cube_alias: str,
        node_name: str,
        *,
        projects_dir: Path | None = None,
    ) -> bool:
        """Refresh one picker from the authoritative workflow asset path."""

        workflow = self._active_workflow()
        panel = self._active_panel()
        if workflow is None or panel is None:
            return False
        if (
            self._preview_coordinator is not None
            and self._preview_coordinator.mask_preview_mounted(
                panel,
                cube_alias,
                node_name,
            )
        ):
            return True
        workflow_id = self._workflow_session.active_workflow_id
        resolved_path = self._workflow_inputs.resolve_input_mask_path(
            workflow,
            workflow_name=self._workflow_name(workflow_id),
            section_key=cube_alias,
            node_name=node_name,
            projects_dir=projects_dir or self._projects_dir(),
        )
        if resolved_path is None or not resolved_path.exists():
            return False
        panel.refresh_mask_picker(cube_alias, node_name, str(resolved_path))
        log_debug(
            _LOGGER,
            "Refreshed mask picker from workflow asset state",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            node_name=node_name,
            resolved_path=str(resolved_path),
        )
        return True


__all__ = ["InputMaskPickerPresenter"]
