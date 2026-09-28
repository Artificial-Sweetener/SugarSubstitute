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

"""Keep a mounted Cube-stack affordance when its canonical graph becomes empty."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget

from substitute.application.cubes import CubeStackService
from substitute.application.cubes.graph_backed_cube_stack_service import (
    GraphBackedCubeStackService,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.shell.workflow_ui_factory import WorkflowUiFactory
from substitute.presentation.workflows.segmented_cube_stack import SegmentedCubeStack
from tests.application.cubes.cube_stack.graph_backed_support import (
    _StructuralGraphGateway,
)
from tests.support.canonical_cube_graph import graph_backed_cube_workflow
from tests.support.qt.lifecycle import destroy_qt_object


class _WorkflowSession:
    """Expose one authoritative workflow to the presentation factory."""

    def __init__(self, workflow: WorkflowState) -> None:
        """Register the workflow under a stable route."""

        self.workflows = {"workflow": workflow}


class _MountedStackShell:
    """Mount the real stack in the production factory's Qt container."""

    def __init__(self, workflow: WorkflowState, stack: SegmentedCubeStack) -> None:
        """Store the minimal surface dependencies for stack reconciliation."""

        self.workflow_session_service = _WorkflowSession(workflow)
        self.cube_stack_container = QStackedWidget()
        self.cube_stack_container.setFixedSize(230, 300)
        self.cube_stack_container.addWidget(cast(QWidget, stack))
        self.cube_stacks = {"workflow": stack}
        self.cube_stack: SegmentedCubeStack | None = stack


def test_last_cube_removal_keeps_add_card_mounted_and_clickable(
    qt_application_owner: QApplication,
) -> None:
    """A live empty Cube workflow must still request the picker from its stack."""

    workflow = graph_backed_cube_workflow("Temporary")
    stack = SegmentedCubeStack()
    shell = _MountedStackShell(workflow, stack)
    requests: list[bool] = []
    stack.cubeAddRequested.connect(lambda: requests.append(True))
    stack.addTab("Temporary", "Temporary")
    shell.cube_stack_container.show()
    qt_application_owner.processEvents()

    try:
        CubeStackService(
            GraphBackedCubeStackService(_StructuralGraphGateway())
        ).apply_cube_removal(workflow, "Temporary")
        stack.removeTab(0)
        mounted = WorkflowUiFactory(shell).reconcile_cube_stack_surface(
            "workflow", set_as_current=True
        )
        qt_application_owner.processEvents()

        assert mounted is stack
        assert shell.cube_stack_container.currentWidget() is cast(QWidget, stack)
        assert stack.addPlaceholder.isVisibleTo(shell.cube_stack_container)

        QTest.mouseClick(stack.addPlaceholder, Qt.MouseButton.LeftButton)
        assert requests == [True]
    finally:
        shell.cube_stack_container.close()
        destroy_qt_object(shell.cube_stack_container)
