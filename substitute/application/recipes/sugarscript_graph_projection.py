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

"""Project lossless Cube-only graph persistence into SugarScript edges."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.comfy_workflow.cube_analysis import CubeGraphEdgeOrigin
from substitute.domain.recipes.sugar_script_serializer import (
    SugarScriptCubeConnection,
)


def explicit_sugarscript_connections(
    direct: DirectWorkflowState | None,
) -> tuple[SugarScriptCubeConnection, ...]:
    """Return explicit Cube edges or reject a lossy non-Cube graph conversion."""

    if direct is None:
        return ()
    analysis = direct.cube_analysis
    if analysis is None:
        raise ValueError(
            "Canonical Cube graph analysis is required for SugarScript save."
        )
    nodes = direct.source_workflow.get("nodes")
    if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
        raise ValueError(
            "Canonical workflow nodes are unavailable for SugarScript save."
        )
    cube_node_ids = {instance.node_id for instance in analysis.instances}
    root_node_ids = {
        str(node["id"])
        for node in nodes
        if isinstance(node, Mapping)
        and "id" in node
        and not isinstance(node["id"], bool)
        and isinstance(node["id"], str | int)
    }
    if root_node_ids != cube_node_ids:
        raise ValueError(
            "SugarScript cannot losslessly save a workflow with non-Cube graph segments."
        )
    aliases_by_instance = {
        instance.instance_id: instance.alias for instance in analysis.instances
    }
    result: list[SugarScriptCubeConnection] = []
    for edge in analysis.edges:
        if edge.origin is not CubeGraphEdgeOrigin.EXPLICIT:
            continue
        source_alias = aliases_by_instance.get(edge.source_instance_id)
        target_alias = aliases_by_instance.get(edge.target_instance_id)
        if source_alias is None or target_alias is None:
            raise ValueError("Canonical Cube edge references an unknown instance.")
        result.append(
            SugarScriptCubeConnection(
                source_alias=source_alias,
                source_binding=edge.source_binding,
                target_alias=target_alias,
                target_binding=edge.target_binding,
            )
        )
    return tuple(result)


__all__ = ["explicit_sugarscript_connections"]
