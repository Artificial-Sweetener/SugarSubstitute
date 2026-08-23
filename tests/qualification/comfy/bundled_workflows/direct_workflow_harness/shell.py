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

"""Mount and control one production shell for direct-workflow qualifications."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtWidgets import QApplication, QWidget

from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import WorkflowDocumentKind, WorkflowState
from substitute.presentation.cubes.cube_stack_metrics import CUBE_STACK_EXPANDED_WIDTH
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


class DirectWorkflowShell:
    """Own one mounted cube/direct workflow shell and its Qt lifecycle."""

    def __init__(self, artifact_root: Path) -> None:
        """Mount the production shell below the caller-owned artifact root."""

        self._base = PromptEditorRealShellScenario(artifact_root=artifact_root)
        self._previous_reduced_motion = self._base.app.property(
            "substitute.reduce_motion"
        )
        self._base.app.setProperty("substitute.reduce_motion", False)
        self.shell = self._base.shell
        cube_field = self._base.workflows.add_prompt_workflow("cube", activate=True)
        self.cube_workflow_id = cube_field.workflow.workflow_id
        self.direct_workflow_id = "workflow-direct"
        direct_workflow = WorkflowState(
            direct_workflow=DirectWorkflowState(
                source_path=Path("direct-workflow.json"),
                source_workflow={"nodes": []},
                buffer={"nodes": {}},
            )
        )
        self.shell.workflow_session_service.add_existing_workflow(
            self.direct_workflow_id,
            direct_workflow,
            activate=False,
        )
        self.shell.workflow_tabbar.addTab(self.direct_workflow_id, "Direct")
        self.shell.install_workflow_surface(self.direct_workflow_id)
        self.shell.splitter.setSizes([760, 520])
        self.process_events()
        self.activate_cube(animated=False)

    @property
    def app(self) -> QApplication:
        """Return the application owned by the mounted shell scenario."""

        return self._base.app

    def close(self) -> None:
        """Close the mounted shell and restore its process-local Qt setting."""

        self._base.app.setProperty(
            "substitute.reduce_motion",
            self._previous_reduced_motion,
        )
        self._base.close()

    def activate_cube(self, *, animated: bool = True) -> None:
        """Activate the cube route through its production presentation owner."""

        if animated:
            self.shell.workflow_workspace.activate_workflow(
                self.cube_workflow_id,
                force_refresh=True,
                source="direct-harness-cube",
            )
        else:
            self.shell.workflow_session_service.activate_workflow(self.cube_workflow_id)
            self.shell.editor_panel_container.setCurrentWidget(
                self.shell.editor_panels[self.cube_workflow_id]
            )
            self.shell.cube_stack_container.setCurrentWidget(
                cast(QWidget, self.shell.cube_stacks[self.cube_workflow_id])
            )
            self.shell.cube_stack_presentation_controller.activate_document_kind(
                WorkflowDocumentKind.CUBE_STACK,
                animated=False,
            )
        self.process_events()

    def activate_direct(self, *, animated: bool = True) -> None:
        """Activate the direct route through its production presentation owner."""

        if animated:
            self.shell.workflow_workspace.activate_workflow(
                self.direct_workflow_id,
                force_refresh=True,
                source="direct-harness-direct",
            )
        else:
            self.shell.workflow_session_service.activate_workflow(
                self.direct_workflow_id
            )
            self.shell.editor_panel_container.setCurrentWidget(
                self.shell.editor_panels[self.direct_workflow_id]
            )
            self.shell.workflow_ui_factory.reconcile_cube_stack_surface(
                self.direct_workflow_id,
                set_as_current=True,
            )
            self.shell.cube_stack_presentation_controller.activate_document_kind(
                WorkflowDocumentKind.DIRECT_COMFY,
                animated=False,
            )
        self.process_events()

    def wait_for_transition(self, timeout_ms: int = 2000) -> None:
        """Wait for the presentation owner to reach a settled state."""

        wait_for_qt_condition(
            lambda: not self.shell.cube_stack_presentation_controller.is_animating,
            timeout_ms=timeout_ms,
        )
        self.process_events()

    def wait_for_intermediate_transition(self, timeout_ms: int = 2000) -> None:
        """Wait for a measurable intermediate cube-stack presentation frame."""

        self.wait_until(
            lambda: (
                self.shell.cube_stack_presentation_controller.is_animating
                and 0
                < self.shell.cube_stack_presentation_controller.current_frame().container_width
                < CUBE_STACK_EXPANDED_WIDTH
            ),
            description="cube-stack intermediate presentation frame",
            timeout_ms=timeout_ms,
        )

    def wait_until(
        self,
        predicate: Callable[[], bool],
        *,
        description: str,
        timeout_ms: int = 2000,
    ) -> None:
        """Wait for observable production state without scheduler-based delays."""

        _ = description
        wait_for_qt_condition(predicate, timeout_ms=timeout_ms)
        self.process_events()

    def process_events(self) -> None:
        """Flush queued route, layout, visibility, and paint work."""

        self._base.wait_for_queued_delivery()
