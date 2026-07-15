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

"""Resolve the shell's currently active workflow and presentation surfaces."""

from __future__ import annotations

from typing import Any, cast

from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.workflows.cube_stack_view import CubeStack


class ShellActiveSurfaceController:
    """Own active workflow, editor, cube-stack, and override-manager lookups."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose active widget containers should be inspected."""

        self._shell = shell

    def get_active_workflow(self) -> object:
        """Return the currently active workflow session model."""

        return self._shell.workflow_session_service.get_active_workflow()

    def active_editor_panel(self) -> EditorPanel | None:
        """Return the currently visible editor panel."""

        if not hasattr(self._shell, "editor_panel_container"):
            return None
        current_widget = self._shell.editor_panel_container.currentWidget()
        return current_widget if isinstance(current_widget, EditorPanel) else None

    def active_cube_stack(self) -> CubeStack | None:
        """Return the currently visible cube stack."""

        if not hasattr(self._shell, "cube_stack_container"):
            return None
        current_widget = self._shell.cube_stack_container.currentWidget()
        return current_widget if isinstance(current_widget, CubeStack) else None

    def active_override_manager(self) -> object | None:
        """Return the override manager for the currently active workflow."""

        if not hasattr(self._shell, "override_managers"):
            return None
        active_id = self._shell.workflow_session_service.active_workflow_id
        return cast(object | None, self._shell.override_managers.get(active_id))


__all__ = ["ShellActiveSurfaceController"]
