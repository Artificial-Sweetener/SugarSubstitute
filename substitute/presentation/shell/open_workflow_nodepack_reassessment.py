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

"""Reassess the active saved workflow when its Comfy runtime changes."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QObject, QTimer

from substitute.application.comfy_nodepacks.workflow_node_definition_assessment import (
    WorkflowNodeDefinitionAssessment,
)
from substitute.domain.comfy_connection import (
    ComfyConnectionPhase,
    ComfyConnectionStateChange,
)

from .direct_workflow_nodepack_recovery import (
    DirectWorkflowNodepackRecoveryController,
)

if TYPE_CHECKING:
    from .main_window import MainWindow


class OpenWorkflowNodepackReassessment:
    """Keep one visible workflow's node cards aligned with live Comfy metadata."""

    def __init__(
        self,
        *,
        shell: MainWindow,
        recovery: DirectWorkflowNodepackRecoveryController,
    ) -> None:
        """Store the shell's active workflow and recovery collaborators."""

        self._shell = shell
        self._recovery = recovery

    def observe_connection(self, change: ComfyConnectionStateChange) -> None:
        """Recheck the open workflow against a newly ready Comfy process."""

        if (
            change.current.phase is ComfyConnectionPhase.READY
            and change.previous.phase is not ComfyConnectionPhase.READY
        ):
            self.reassess_active()

    def schedule_after_restore(self) -> None:
        """Wait until the restored shell is revealed before offering repair."""

        QTimer.singleShot(0, cast(QObject, self._shell), self.reassess_active)

    def reassess_active(self) -> None:
        """Resolve the current canonical graph without requiring a fresh file load."""

        session = self._shell.workflow_session_service
        workflow_id = session.active_workflow_id
        if not workflow_id:
            return
        state = session.workflows.get(workflow_id)
        document = state.direct_workflow if state is not None else None
        if document is None:
            return
        workflow = document.source_workflow

        def refresh_projection(assessment: WorkflowNodeDefinitionAssessment) -> None:
            """Rebuild only the still-open workflow from assessed live definitions."""

            current = session.workflows.get(workflow_id)
            if (
                current is None
                or current.direct_workflow is None
                or current.direct_workflow.source_workflow is not workflow
            ):
                return
            panel = self._shell.editor_panels.get(workflow_id)
            if panel is None:
                return
            classes = tuple(
                sorted(
                    {
                        node.class_type
                        for node in (*assessment.available, *assessment.missing)
                    }
                )
            )
            if classes:
                panel.refresh_projection_after_node_definition_update(
                    refreshed_node_classes=classes
                )

        self._recovery.reassess_open_workflow(
            workflow=workflow,
            target_workflow_id=workflow_id,
            refresh_projection=refresh_projection,
        )


__all__ = ["OpenWorkflowNodepackReassessment"]
