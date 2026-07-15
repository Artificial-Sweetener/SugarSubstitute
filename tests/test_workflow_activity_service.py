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

"""Contract tests for session-scoped workflow activity state."""

from __future__ import annotations

from substitute.application.workflows import WorkflowActivityService


def test_workflow_activity_marks_only_inactive_outputs_unread() -> None:
    """Output activity should mark inactive workflows and ignore active workflow."""

    service = WorkflowActivityService()

    assert service.record_output("wf-a", "wf-a") is False
    assert service.has_unread_result("wf-a") is False
    assert service.record_output("wf-b", "wf-a") is True
    assert service.has_unread_result("wf-b") is True
    assert service.record_output("wf-b", "wf-a") is False


def test_workflow_activity_clears_rekeys_and_removes_unread_state() -> None:
    """Workflow lifecycle operations should keep activity keys aligned."""

    service = WorkflowActivityService()
    service.record_output("wf-b", "wf-a")

    service.rename_workflow("wf-b", "wf-c")
    assert service.has_unread_result("wf-b") is False
    assert service.has_unread_result("wf-c") is True
    assert service.mark_seen("wf-c") is True
    assert service.has_unread_result("wf-c") is False

    service.record_output("wf-d", "wf-a")
    service.remove_workflow("wf-d")
    assert service.has_unread_result("wf-d") is False
