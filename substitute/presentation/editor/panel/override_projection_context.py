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

"""Resolve workflow and behavior context for global override projections."""

from __future__ import annotations

from typing import Any

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.overrides import OverrideToolbarSnapshot
from substitute.application.workflows.editor_projection_service import (
    WorkflowEditorProjection,
    WorkflowEditorProjectionService,
)
from substitute.presentation.editor.panel.override_workflow_state import (
    OverrideWorkflowState,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.editor.panel.override_projection_context")


class OverrideProjectionContext:
    """Resolve current editor context without owning workflow override state."""

    def __init__(self, mainwindow: Any) -> None:
        """Capture the shell and unified workflow projection service."""

        self._mainwindow = mainwindow
        self._projection_service = WorkflowEditorProjectionService()

    def behavior_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Return the latest application-owned editor behavior snapshot."""

        panel = self._mainwindow.active_editor_panel
        if panel is None:
            return None
        if hasattr(panel, "current_behavior_snapshot"):
            snapshot = panel.current_behavior_snapshot()
            return snapshot if isinstance(snapshot, EditorBehaviorSnapshot) else None
        snapshot = getattr(panel, "_last_behavior_snapshot", None)
        return snapshot if isinstance(snapshot, EditorBehaviorSnapshot) else None

    def editor_projection(self) -> WorkflowEditorProjection | None:
        """Return the unified graph-state projection for the active document."""

        workflow = self._mainwindow.get_active_workflow()
        if workflow is None:
            return None
        return self._projection_service.project(workflow)

    def projection_order(self) -> tuple[str, ...]:
        """Return the active editor section order for override discovery."""

        projection = self.editor_projection()
        return projection.order if projection is not None else ()

    def toolbar_snapshot(
        self,
        workflow_state: OverrideWorkflowState,
    ) -> OverrideToolbarSnapshot:
        """Build a toolbar snapshot from the current workflow and behavior context."""

        workflow = self._mainwindow.get_active_workflow()
        behavior_snapshot = self.behavior_snapshot()
        stack_order = self.projection_order()
        log_debug(
            _LOGGER,
            "refresh toolbar snapshot requested",
            workflow_present=workflow is not None,
            behavior_snapshot_present=behavior_snapshot is not None,
            stack_order=stack_order,
            override_keys=tuple(sorted(workflow_state.overrides)),
        )
        if workflow is None or behavior_snapshot is None:
            return OverrideToolbarSnapshot([], [], ())
        snapshot = workflow_state.build_toolbar_snapshot(
            behavior_snapshot=behavior_snapshot,
            stack_order=stack_order,
        )
        log_debug(
            _LOGGER,
            "refresh toolbar snapshot completed",
            candidate_count=len(snapshot.candidates),
            active_control_count=len(snapshot.active_controls),
            active_override_keys=snapshot.active_override_keys,
        )
        return snapshot


__all__ = ["OverrideProjectionContext"]
