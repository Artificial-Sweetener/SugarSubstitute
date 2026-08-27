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

"""Project scalar mask picker refresh identities from semantic canvas plans."""

from __future__ import annotations

from collections.abc import Callable

from substitute.domain.workflow import (
    InputAssetCardinality,
    InputCanvasPlan,
    WorkflowState,
)


def scalar_mask_picker_identities(
    workflow: WorkflowState,
    plan_for_section: Callable[[WorkflowState, str], InputCanvasPlan],
) -> tuple[tuple[str, str], ...]:
    """Return scalar mask nodes recognized by each cube's live semantics."""

    identities: list[tuple[str, str]] = []
    for section_key in workflow.cubes:
        plan = plan_for_section(workflow, section_key)
        identities.extend(
            (section_key, binding.mask_endpoint.node_name)
            for binding in plan.mask_bindings
            if binding.mask_endpoint.cardinality is InputAssetCardinality.SCALAR
        )
    return tuple(dict.fromkeys(identities))


__all__ = ["scalar_mask_picker_identities"]
