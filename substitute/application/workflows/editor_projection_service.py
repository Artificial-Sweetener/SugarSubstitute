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

"""Project workflow document kinds into the shared editor-section contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

DIRECT_WORKFLOW_SECTION_KEY = "__direct_comfy_workflow__"


@dataclass(frozen=True, slots=True)
class WorkflowEditorProjection:
    """Carry ordered graph states consumed by the unified editor panel."""

    states: Mapping[str, object]
    order: tuple[str, ...]

    @property
    def entries(self) -> tuple[tuple[str, object], ...]:
        """Return section states in projection order."""

        return tuple((key, self.states[key]) for key in self.order)


class WorkflowEditorProjectionService:
    """Select cube sections or one direct graph section for an editor document."""

    def project(self, workflow: object) -> WorkflowEditorProjection:
        """Return the mutually exclusive editor representation of a workflow tab."""

        direct_workflow = getattr(workflow, "direct_workflow", None)
        cubes = getattr(workflow, "cubes", {})
        stack_order = getattr(workflow, "stack_order", ())
        if direct_workflow is not None:
            if cubes or stack_order:
                raise ValueError("Direct Comfy workflows cannot be mixed with cubes.")
            return WorkflowEditorProjection(
                states={DIRECT_WORKFLOW_SECTION_KEY: direct_workflow},
                order=(DIRECT_WORKFLOW_SECTION_KEY,),
            )
        if not isinstance(cubes, Mapping):
            raise TypeError("Workflow cube state must be a mapping.")
        order = tuple(str(alias) for alias in stack_order)
        return WorkflowEditorProjection(states=cubes, order=order)


__all__ = [
    "DIRECT_WORKFLOW_SECTION_KEY",
    "WorkflowEditorProjection",
    "WorkflowEditorProjectionService",
]
