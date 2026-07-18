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

"""Collect backend node classes referenced by Comfy UI workflow documents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .node_roles import WorkflowNodeExecutionRole, known_execution_role


def executable_node_classes(
    workflow: Mapping[str, object],
) -> tuple[str, ...]:
    """Return sorted backend classes across the root graph and local subgraphs."""

    definitions = workflow.get("definitions")
    subgraphs: tuple[Mapping[str, object], ...] = ()
    if isinstance(definitions, Mapping):
        subgraphs = _mapping_records(definitions.get("subgraphs"))
    subgraph_ids = {
        str(subgraph_id)
        for subgraph in subgraphs
        if isinstance((subgraph_id := subgraph.get("id")), str)
    }
    class_types: set[str] = set()
    for node in (
        *_mapping_records(workflow.get("nodes")),
        *(
            node
            for subgraph in subgraphs
            for node in _mapping_records(subgraph.get("nodes"))
        ),
    ):
        class_type = node.get("type")
        if not isinstance(class_type, str):
            continue
        normalized = class_type.strip()
        if (
            normalized
            and normalized not in subgraph_ids
            and known_execution_role(normalized) is WorkflowNodeExecutionRole.EXECUTABLE
        ):
            class_types.add(normalized)
    return tuple(sorted(class_types))


def _mapping_records(payload: object) -> tuple[Mapping[str, object], ...]:
    """Return mapping records from one serialized array."""

    if not isinstance(payload, Sequence) or isinstance(payload, str | bytes):
        return ()
    return tuple(item for item in payload if isinstance(item, Mapping))


__all__ = ["executable_node_classes"]
