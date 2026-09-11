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

"""Project authoritative Cube presentation labels onto stable graph instances."""

from __future__ import annotations

from substitute.application.cubes import (
    build_cube_tab_presentation,
    cube_target_model,
)
from substitute.domain.workflow import WorkflowState


def native_cube_presentation_labels(
    workflow: object | None,
) -> dict[str, str]:
    """Return display labels keyed by SugarCubes stable instance identity."""

    if not isinstance(workflow, WorkflowState) or workflow.direct_workflow is None:
        return {}
    analysis = workflow.direct_workflow.cube_analysis
    if analysis is None:
        return {}
    labels: dict[str, str] = {}
    for instance in analysis.instances:
        cube = workflow.cubes.get(instance.alias)
        if cube is None:
            continue
        presentation = build_cube_tab_presentation(
            alias=cube.alias,
            cube_id=cube.cube_id,
            version=cube.version,
            target_model=cube_target_model(cube),
        )
        labels[instance.instance_id] = presentation.primary_text
    return labels


__all__ = ["native_cube_presentation_labels"]
