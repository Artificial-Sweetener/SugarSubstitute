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

"""Project authoritative generation seed changes into mounted controls."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QSignalBlocker

from substitute.application.generation import SeedRandomizationResult
from substitute.presentation.widgets import SeedBox


class SeedValueProjector:
    """Synchronize active SeedBoxes from application-owned seed changes."""

    def __init__(self, shell: object) -> None:
        """Store the shell whose active workflow controls are projected."""

        self._shell = shell

    def project(self, workflow: object, result: SeedRandomizationResult) -> None:
        """Project changes only when their workflow owns the active surface."""

        if not result.changed or not self._is_active_workflow(workflow):
            return
        panel = getattr(self._shell, "active_editor_panel", None)
        cube_widgets = getattr(panel, "cube_widgets", None)
        for change in result.changes:
            if change.override_key is not None:
                self._project_override_seed(change.value)
                continue
            if not isinstance(cube_widgets, Mapping) or change.cube_alias is None:
                continue
            cube_widget = cube_widgets.get(change.cube_alias)
            if cube_widget is None:
                continue
            self._project_node_seed(
                cube_widget,
                node_name=change.node_name,
                field_key=change.field_key,
                value=change.value,
            )

    def _is_active_workflow(self, workflow: object) -> bool:
        """Return whether the randomized workflow backs the active shell surface."""

        get_active_workflow = getattr(self._shell, "get_active_workflow", None)
        return not callable(get_active_workflow) or get_active_workflow() is workflow

    def _project_override_seed(self, value: int) -> None:
        """Project the authoritative global override seed when its control exists."""

        manager = getattr(self._shell, "active_override_manager", None)
        project = getattr(manager, "project_seed_value_from_workflow", None)
        if callable(project):
            project(value)

    @staticmethod
    def _project_node_seed(
        cube_widget: object,
        *,
        node_name: str | None,
        field_key: str,
        value: int,
    ) -> None:
        """Project one node seed into its metadata-identified SeedBox."""

        find_children = getattr(cube_widget, "findChildren", None)
        if not callable(find_children):
            return
        for seed_box in find_children(SeedBox):
            metadata = seed_box.property("input_metadata")
            if not isinstance(metadata, Mapping):
                continue
            if (
                metadata.get("node_name") != node_name
                or metadata.get("key") != field_key
            ):
                continue
            blocker = QSignalBlocker(seed_box)
            try:
                seed_box.setValue(value)
            finally:
                del blocker


__all__ = ["SeedValueProjector"]
