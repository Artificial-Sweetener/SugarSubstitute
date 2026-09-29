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

"""Project authored Cube order into stable Output canvas source identities."""

from __future__ import annotations

from substitute.domain.workflow import WorkflowState


def authored_output_source_keys(workflow: WorkflowState) -> tuple[str, ...]:
    """Return source keys for visible Cubes in the current authored stack."""

    document = workflow.direct_workflow
    analysis = document.cube_analysis if document is not None else None
    if analysis is None:
        return tuple(f"cube:{alias}" for alias in workflow.stack_order)
    instance_by_alias = {instance.alias: instance for instance in analysis.instances}
    return tuple(
        f"cube:{instance_by_alias[alias].instance_id}"
        for alias in workflow.stack_order
        if alias in instance_by_alias
    )


__all__ = ["authored_output_source_keys"]
