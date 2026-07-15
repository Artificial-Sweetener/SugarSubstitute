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

"""Capture live workspace state through presentation-owned ports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from substitute.domain.session import (
    SESSION_SNAPSHOT_SCHEMA_VERSION,
    SessionSnapshot,
)
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    ShellLayoutSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.workspace_state.snapshot_capture_service")


class SnapshotCapturePort(Protocol):
    """Describe live shell state needed to capture a restorable session."""

    def workflow_ids_in_order(self) -> tuple[str, ...]:
        """Return workflow ids in visual tab order."""

    def active_workspace_route(self) -> str:
        """Return the current workspace route key."""

    def active_workflow_id(self) -> str:
        """Return the active workflow id beneath the current route."""

    def workflow_state(self, workflow_id: str) -> WorkflowState | None:
        """Return the workflow state for one id."""

    def workflow_tab_label(self, workflow_id: str) -> str:
        """Return the tab label for one workflow id."""

    def active_cube_alias(self, workflow_id: str) -> str | None:
        """Return the active cube alias for one workflow."""

    def input_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputImageReference, ...]:
        """Return restorable input image references for one workflow."""

    def input_mask_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputMaskReference, ...]:
        """Return restorable input mask references for one workflow."""

    def output_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[OutputImageReference, ...]:
        """Return restorable output image references for one workflow."""

    def editor_viewport_snapshot(
        self,
        workflow_id: str,
    ) -> EditorViewportSnapshot | None:
        """Return restorable editor viewport state for one workflow."""

    def shell_layout_snapshot(self) -> ShellLayoutSnapshot | None:
        """Return restorable shell layout state."""


@dataclass(frozen=True, slots=True)
class SnapshotCaptureService:
    """Capture a process-local session snapshot from presentation ports."""

    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)

    def capture(self, port: SnapshotCapturePort) -> SessionSnapshot:
        """Capture one complete session snapshot."""

        workflow_ids = port.workflow_ids_in_order()
        active_route = port.active_workspace_route()
        active_workflow_id = port.active_workflow_id()
        log_debug(
            _LOGGER,
            "snapshot capture started",
            workflow_ids=workflow_ids,
            active_route=active_route,
            active_workflow_id=active_workflow_id,
        )
        workflows: list[WorkflowSnapshot] = []
        for workflow_id in workflow_ids:
            workflow = port.workflow_state(workflow_id)
            if workflow is None:
                log_debug(
                    _LOGGER,
                    "snapshot capture skipped missing workflow",
                    workflow_id=workflow_id,
                )
                continue
            tab_label = port.workflow_tab_label(workflow_id)
            active_cube_alias = port.active_cube_alias(workflow_id)
            input_images = port.input_image_references(workflow_id, workflow)
            input_masks = port.input_mask_references(workflow_id, workflow)
            output_images = port.output_image_references(workflow_id, workflow)
            editor_viewport = port.editor_viewport_snapshot(workflow_id)
            log_debug(
                _LOGGER,
                "snapshot capture workflow",
                workflow_id=workflow_id,
                tab_label=tab_label,
                active_cube_alias=active_cube_alias,
                cube_count=len(workflow.cubes),
                stack_order=tuple(workflow.stack_order),
                input_image_count=len(input_images),
                input_mask_count=len(input_masks),
                output_image_count=len(output_images),
                editor_viewport_present=editor_viewport is not None,
            )
            workflows.append(
                WorkflowSnapshot(
                    workflow_id=workflow_id,
                    tab_label=tab_label,
                    workflow=workflow,
                    active_cube_alias=active_cube_alias,
                    input_images=input_images,
                    input_masks=input_masks,
                    output_images=output_images,
                    editor_viewport=editor_viewport,
                )
            )
        shell_layout = port.shell_layout_snapshot()
        log_debug(
            _LOGGER,
            "snapshot capture received shell layout",
            shell_layout_present=shell_layout is not None,
            captured_main_splitter_sizes=tuple(shell_layout.main_splitter_sizes)
            if shell_layout is not None
            else (),
            captured_editor_output_splitter_sizes=tuple(
                shell_layout.editor_output_splitter_sizes
            )
            if shell_layout is not None
            else (),
            captured_cube_stack_compact=shell_layout.cube_stack_compact
            if shell_layout is not None
            else None,
            captured_cube_stack_width=shell_layout.cube_stack_width
            if shell_layout is not None
            else None,
            captured_editor_panel_width=shell_layout.editor_panel_width
            if shell_layout is not None
            else None,
            captured_canvas_panel_width=shell_layout.canvas_panel_width
            if shell_layout is not None
            else None,
            captured_side_panel_width=shell_layout.side_panel_width
            if shell_layout is not None
            else None,
            captured_output_panel_height=shell_layout.output_panel_height
            if shell_layout is not None
            else None,
            active_route=active_route,
            active_workflow_id=active_workflow_id,
        )
        log_debug(
            _LOGGER,
            "snapshot capture completed",
            captured_workflow_ids=tuple(workflow.workflow_id for workflow in workflows),
            active_route=active_route,
            active_workflow_id=active_workflow_id,
            shell_layout_present=shell_layout is not None,
        )
        return SessionSnapshot(
            schema_version=SESSION_SNAPSHOT_SCHEMA_VERSION,
            captured_at=self.clock(),
            workspace=WorkspaceSnapshot(
                schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
                workflows=tuple(workflows),
                tab_order=tuple(workflow.workflow_id for workflow in workflows),
                active_route=active_route,
                active_workflow_id=active_workflow_id,
                shell_layout=shell_layout,
            ),
        )


__all__ = [
    "SnapshotCapturePort",
    "SnapshotCaptureService",
]
