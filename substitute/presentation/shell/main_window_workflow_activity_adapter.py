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

"""Adapt MainWindow workflow activity to its narrow lifecycle port."""

from __future__ import annotations


from substitute.shared.logging.logger import (
    get_logger,
)

_LOGGER = get_logger("presentation.shell.main_window_workflow_activity_adapter")
_RECONCILER_LOGGER = get_logger("presentation.shell.workflow_surface_reconciler")


class MainWindowWorkflowActivityAdapter:
    """Expose workflow activity badge updates through a narrow port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind an activity API."""

        self._shell = shell

    def mark_workflow_seen(self, workflow_id: str) -> bool:
        """Clear unread workflow result state when the shell exposes it."""

        activity_service = getattr(self._shell, "workflow_activity_service", None)
        mark_seen = getattr(activity_service, "mark_seen", None)
        if not callable(mark_seen) or not bool(mark_seen(workflow_id)):
            return False
        tabbar = getattr(self._shell, "workflow_tabbar", None)
        set_unread = getattr(tabbar, "set_workflow_unread_result", None)
        if callable(set_unread):
            set_unread(workflow_id, False)
        return True
