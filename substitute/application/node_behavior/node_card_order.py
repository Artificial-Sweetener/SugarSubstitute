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

"""Compute deterministic graph order and reachability for editor node cards."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping


def wired_node_order(nodes: Mapping[str, object]) -> list[str]:
    """Return deterministic upstream-before-downstream node order."""

    node_names = [name for name in nodes if isinstance(name, str)]
    in_degree = {name: 0 for name in node_names}
    graph = downstream_node_graph(nodes)

    for node_name, node_data in nodes.items():
        if not isinstance(node_name, str) or not isinstance(node_data, Mapping):
            continue
        inputs = node_data.get("inputs", {})
        if not isinstance(inputs, Mapping):
            continue
        for input_value in inputs.values():
            if not _is_local_node_link(input_value, in_degree):
                continue
            in_degree[node_name] += 1

    queue = deque(name for name in node_names if in_degree[name] == 0)
    ordered: list[str] = []
    while queue:
        current = queue.popleft()
        ordered.append(current)
        for dependent in graph[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    ordered.extend(name for name in node_names if name not in ordered)
    return ordered


def downstream_node_graph(nodes: Mapping[str, object]) -> dict[str, tuple[str, ...]]:
    """Return local source-to-dependent adjacency in persisted node order."""

    node_names = {name for name in nodes if isinstance(name, str)}
    dependents: dict[str, list[str]] = {name: [] for name in node_names}
    for node_name, node_data in nodes.items():
        if not isinstance(node_name, str) or not isinstance(node_data, Mapping):
            continue
        inputs = node_data.get("inputs", {})
        if not isinstance(inputs, Mapping):
            continue
        for input_value in inputs.values():
            if _is_local_node_link(input_value, dependents):
                dependents[input_value[0]].append(node_name)
    return {name: tuple(items) for name, items in dependents.items()}


def node_reaches(
    graph: Mapping[str, tuple[str, ...]],
    source: str,
    target: str,
) -> bool:
    """Return whether target is downstream of source without recursing through cycles."""

    if source == target:
        return True
    visited = {source}
    pending = list(graph.get(source, ()))
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(graph.get(current, ()))
    return False


def _is_local_node_link(
    input_value: object,
    node_names: Mapping[str, object],
) -> bool:
    """Return whether one input value links to another node in the same cube."""

    return (
        isinstance(input_value, list)
        and bool(input_value)
        and isinstance(input_value[0], str)
        and input_value[0] in node_names
    )


__all__ = [
    "downstream_node_graph",
    "node_reaches",
    "wired_node_order",
]
