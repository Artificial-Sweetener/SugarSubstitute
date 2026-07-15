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

"""Adapt shell workflow chrome for Input canvas collaborators."""

from __future__ import annotations

from substitute.presentation.shell.workflow_surface_invalidation import (
    CANVAS_AND_GENERATION_SURFACES,
    WorkflowInvalidationReason,
)


class InputCanvasShellAdapter:
    """Provide shell-owned workflow naming and invalidation for Input canvas code."""

    def __init__(self, shell: object) -> None:
        """Store the shell object that owns workflow tabs and dirty state."""

        self._shell = shell

    def resolve_workflow_name(self, workflow_id: str) -> str:
        """Resolve the current workflow tab label for output directory naming."""

        workflow_tabbar = getattr(self._shell, "workflow_tabbar", None)
        item_map = getattr(workflow_tabbar, "itemMap", {})
        tab_item = item_map.get(workflow_id) if hasattr(item_map, "get") else None
        if tab_item is not None:
            text = getattr(tab_item, "text", None)
            workflow_name = str(text()).strip() if callable(text) else ""
            if workflow_name:
                return workflow_name
        return "untitled_workflow"

    def mark_input_canvas_changed(self, workflow_id: str) -> None:
        """Mark Input canvas surfaces dirty after presenter-owned mutations."""

        service = getattr(self._shell, "workflow_surface_invalidation_service", None)
        mark_dirty = getattr(service, "mark_dirty", None)
        if callable(mark_dirty):
            mark_dirty(
                workflow_id,
                CANVAS_AND_GENERATION_SURFACES,
                WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
            )


__all__ = ["InputCanvasShellAdapter"]
