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

"""Characterization tests for workflow-tab rename mapping policies."""

from __future__ import annotations

from substitute.application.workflows import WorkflowSessionService, WorkflowTabService
from substitute.domain.workflow import WorkflowState


def test_rekey_workflow_scoped_maps_updates_all_registered_mappings() -> None:
    """Re-key helper should update every workflow-scoped mapping in place."""
    service = WorkflowTabService()
    editor_panels = {"workflow_1": object()}
    cube_stacks = {"workflow_1": object()}
    override_managers = {"workflow_1": object()}

    service.rekey_workflow_scoped_maps(
        old_workflow_id="workflow_1",
        new_workflow_id="workflow_2",
        mappings=(editor_panels, cube_stacks, override_managers),
    )

    assert "workflow_1" not in editor_panels
    assert "workflow_1" not in cube_stacks
    assert "workflow_1" not in override_managers
    assert "workflow_2" in editor_panels
    assert "workflow_2" in cube_stacks
    assert "workflow_2" in override_managers


def test_session_rename_updates_workflow_map_and_active_key() -> None:
    """Session rename should move workflow entry and track active workflow id."""
    session_service = WorkflowSessionService(WorkflowState)
    creation = session_service.add_workflow("workflow_12345", activate=True)

    renamed = session_service.rename_workflow("workflow_12345", "Recipe Renamed")

    assert renamed is not None
    assert renamed.active_changed is True
    assert "workflow_12345" not in session_service.workflows
    assert session_service.workflows["Recipe Renamed"] is creation.workflow
    assert session_service.active_workflow_id == "Recipe Renamed"
