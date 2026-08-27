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

"""Verify workflow-lifecycle services are composed by their shell owner."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from substitute.presentation.shell import main_window_composition


class _WorkflowLifecycleService:
    """Represent one zero-argument workflow-lifecycle collaborator."""


class _NodeDefinitionRefreshController:
    """Capture the shell that owns node-definition refresh coordination."""

    def __init__(self, shell: object) -> None:
        """Retain the shell supplied during composition."""

        self.shell = shell


@dataclass
class _Shell:
    """Hold workflow-lifecycle collaborators assigned during composition."""

    closed_workflow_buffer: object | None = None
    closed_workflow_snapshot_service: object | None = None
    workflow_activity_service: object | None = None
    node_definition_refresh_controller: object | None = None


def test_compose_workflow_lifecycle_services_assigns_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compose the shell's workflow lifecycle and refresh collaborators."""

    monkeypatch.setattr(
        main_window_composition,
        "ClosedWorkflowBuffer",
        _WorkflowLifecycleService,
    )
    monkeypatch.setattr(
        main_window_composition,
        "ClosedWorkflowSnapshotService",
        _WorkflowLifecycleService,
    )
    monkeypatch.setattr(
        main_window_composition,
        "WorkflowActivityService",
        _WorkflowLifecycleService,
    )
    monkeypatch.setattr(
        main_window_composition,
        "NodeDefinitionRefreshController",
        _NodeDefinitionRefreshController,
    )
    shell = _Shell()

    composition = main_window_composition.compose_workflow_lifecycle_services(shell)

    assert composition.closed_workflow_buffer is shell.closed_workflow_buffer
    assert (
        composition.closed_workflow_snapshot_service
        is shell.closed_workflow_snapshot_service
    )
    assert composition.workflow_activity_service is shell.workflow_activity_service
    assert (
        composition.node_definition_refresh_controller
        is shell.node_definition_refresh_controller
    )
    controller = shell.node_definition_refresh_controller
    assert isinstance(controller, _NodeDefinitionRefreshController)
    assert controller.shell is shell
