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

"""Resolve workflow identity for editor projection collaborators."""

from __future__ import annotations


class EditorProjectionWorkflowContext:
    """Own active workflow-id lookup for editor projection orchestration."""

    def __init__(self, panel: object) -> None:
        """Store the panel whose shell context provides workflow identity."""

        self._panel = panel

    def active_workflow_id(self) -> str:
        """Return the active workflow id when the editor has shell context."""

        mainwindow = getattr(self._panel, "mainwindow", None)
        session_service = getattr(mainwindow, "workflow_session_service", None)
        workflow_id = getattr(session_service, "active_workflow_id", "")
        return str(workflow_id)
