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

"""Track session-scoped workflow activity indicators."""

from __future__ import annotations


class WorkflowActivityService:
    """Own unread-result state for workflow navigation surfaces."""

    def __init__(self) -> None:
        """Create an empty workflow activity tracker."""

        self._unread_result_workflow_ids: set[str] = set()

    def record_output(self, workflow_id: str, active_workflow_id: str) -> bool:
        """Mark an inactive workflow as having unread output."""

        if workflow_id == active_workflow_id:
            return False
        was_unread = workflow_id in self._unread_result_workflow_ids
        self._unread_result_workflow_ids.add(workflow_id)
        return not was_unread

    def mark_seen(self, workflow_id: str) -> bool:
        """Clear unread output state for one workflow."""

        if workflow_id not in self._unread_result_workflow_ids:
            return False
        self._unread_result_workflow_ids.remove(workflow_id)
        return True

    def rename_workflow(self, old_workflow_id: str, new_workflow_id: str) -> None:
        """Re-key unread state after a workflow id rename."""

        if old_workflow_id not in self._unread_result_workflow_ids:
            return
        self._unread_result_workflow_ids.remove(old_workflow_id)
        self._unread_result_workflow_ids.add(new_workflow_id)

    def remove_workflow(self, workflow_id: str) -> None:
        """Drop unread state for a removed workflow."""

        self._unread_result_workflow_ids.discard(workflow_id)

    def has_unread_result(self, workflow_id: str) -> bool:
        """Return whether a workflow currently has unread output."""

        return workflow_id in self._unread_result_workflow_ids


__all__ = ["WorkflowActivityService"]
