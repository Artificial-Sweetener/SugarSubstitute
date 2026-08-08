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

"""Resolve the workflow that authoritatively owns one editor panel."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.domain.workflow import WorkflowState


def workflow_for_panel(panel: object) -> WorkflowState | None:
    """Resolve panel ownership without relying on the currently active route."""

    mainwindow = getattr(panel, "mainwindow", None)
    editor_panels = getattr(mainwindow, "editor_panels", None)
    session_service = getattr(mainwindow, "workflow_session_service", None)
    workflows = getattr(session_service, "workflows", None)
    if not isinstance(editor_panels, Mapping) or not isinstance(workflows, Mapping):
        return None
    workflow_id = next(
        (
            str(candidate_id)
            for candidate_id, candidate_panel in editor_panels.items()
            if candidate_panel is panel
        ),
        None,
    )
    workflow = workflows.get(workflow_id) if workflow_id is not None else None
    return workflow if isinstance(workflow, WorkflowState) else None


__all__ = ["workflow_for_panel"]
