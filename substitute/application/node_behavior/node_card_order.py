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

"""Compute deterministic prompts-first wired order for editor node cards."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence

from substitute.domain.node_behavior import PromptRole
from substitute.domain.node_behavior.inference import prompt_role_from_label


def order_node_cards(
    nodes: Mapping[str, object],
    *,
    layout_nodes: Mapping[str, object] | None = None,
) -> list[str]:
    """Return node names in prompts-first wired card order."""

    ordered = wired_node_order(nodes)
    priority_nodes = prompt_priority_nodes(
        ordered,
        nodes=nodes,
        layout_nodes=layout_nodes,
    )
    return priority_nodes + [name for name in ordered if name not in priority_nodes]


def wired_node_order(nodes: Mapping[str, object]) -> list[str]:
    """Return deterministic upstream-before-downstream node order."""

    node_names = [name for name in nodes if isinstance(name, str)]
    in_degree = {name: 0 for name in node_names}
    graph: dict[str, list[str]] = {name: [] for name in node_names}

    for node_name, node_data in nodes.items():
        if not isinstance(node_name, str) or not isinstance(node_data, Mapping):
            continue
        inputs = node_data.get("inputs", {})
        if not isinstance(inputs, Mapping):
            continue
        for input_value in inputs.values():
            if not _is_local_node_link(input_value, in_degree):
                continue
            dependency = input_value[0]
            graph[dependency].append(node_name)
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


def prompt_priority_nodes(
    ordered_nodes: Sequence[str],
    *,
    nodes: Mapping[str, object],
    layout_nodes: Mapping[str, object] | None = None,
) -> list[str]:
    """Return prompt nodes in positive, negative priority order."""

    priority_nodes: list[str] = []
    resolved_layout_nodes = layout_nodes or {}
    for role in (PromptRole.POSITIVE, PromptRole.NEGATIVE):
        for node_name in ordered_nodes:
            if node_name in priority_nodes:
                continue
            title = node_title_for_order(
                node_name=node_name,
                node_data=nodes.get(node_name),
                layout_nodes=resolved_layout_nodes,
            )
            if title is not None and prompt_role_from_label(title) == role:
                priority_nodes.append(node_name)
    for legacy_name in ("positive_prompt", "negative_prompt"):
        if legacy_name in ordered_nodes and legacy_name not in priority_nodes:
            priority_nodes.append(legacy_name)
    return priority_nodes


def node_title_for_order(
    *,
    node_name: str,
    node_data: object,
    layout_nodes: Mapping[str, object],
) -> str | None:
    """Return the author-facing node title used for prompt role detection."""

    layout_node = layout_nodes.get(node_name)
    if isinstance(layout_node, Mapping):
        layout_title = layout_node.get("title")
        if isinstance(layout_title, str):
            return layout_title
    if isinstance(node_data, Mapping):
        meta = node_data.get("_meta")
        if isinstance(meta, Mapping):
            meta_title = meta.get("title")
            if isinstance(meta_title, str):
                return meta_title
    if node_name in {"positive_prompt", "negative_prompt"}:
        return node_name
    return None


def _is_local_node_link(
    input_value: object,
    node_names: Mapping[str, int],
) -> bool:
    """Return whether one input value links to another node in the same cube."""

    return (
        isinstance(input_value, list)
        and bool(input_value)
        and isinstance(input_value[0], str)
        and input_value[0] in node_names
    )


__all__ = [
    "node_title_for_order",
    "order_node_cards",
    "prompt_priority_nodes",
    "wired_node_order",
]
