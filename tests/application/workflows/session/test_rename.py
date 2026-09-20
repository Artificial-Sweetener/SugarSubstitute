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

"""Verify immutable workflow identity across display-label changes."""

from __future__ import annotations

from substitute.application.workflows import WorkflowSessionService, WorkflowTabService
from substitute.domain.workflow import WorkflowState


def test_label_rename_decision_preserves_session_identity() -> None:
    """A display-label decision must never create a session re-key operation."""

    session = WorkflowSessionService(WorkflowState, default_workflow_id="stable-id")
    workflow = session.get_active_workflow()

    decision = WorkflowTabService().resolve_inline_rename(
        old_workflow_id="stable-id",
        proposed_name="Renamed Workflow",
        existing_labels=(),
    )

    assert decision.accepted is True
    assert decision.workflow_id == "stable-id"
    assert session.active_workflow_id == "stable-id"
    assert session.workflows == {"stable-id": workflow}
