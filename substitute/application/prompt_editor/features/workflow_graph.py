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

"""Provide shared helpers for compiled prompt workflow graph analysis."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.recipes.workflow_payload_nodes import (
    executable_prompt_nodes,
)
from substitute.domain.common import JsonValue


def prompt_node_ids(
    *,
    workflow_payload: Mapping[str, JsonValue],
    cube_alias: str,
    prompt_node_name: str,
) -> tuple[str, ...]:
    """Return compiled node ids matching a Sugar prompt node title."""

    workflow_nodes = executable_prompt_nodes(workflow_payload)
    exact_title = f"{cube_alias}.{prompt_node_name}"
    wrapper_prefix = f"{cube_alias}.{prompt_node_name}."
    matches: list[str] = []
    for node_id, node in workflow_nodes.items():
        if not isinstance(node, Mapping):
            continue
        title = node_title(node)
        if title == exact_title or title.startswith(wrapper_prefix):
            matches.append(str(node_id))
    return tuple(matches)


def upstream_node_ids(
    *,
    workflow_payload: Mapping[str, JsonValue],
    start_node_id: str,
    visited: set[str],
) -> tuple[str, ...]:
    """Return upstream node ids reachable from linked inputs."""

    workflow_nodes = executable_prompt_nodes(workflow_payload)
    return _upstream_node_ids(
        workflow_payload=workflow_nodes,
        start_node_id=start_node_id,
        visited=visited,
    )


def _upstream_node_ids(
    *,
    workflow_payload: Mapping[str, JsonValue],
    start_node_id: str,
    visited: set[str],
) -> tuple[str, ...]:
    """Return upstream node ids from an already-normalized prompt node map."""

    if start_node_id in visited:
        return ()
    visited.add(start_node_id)
    node = workflow_payload.get(start_node_id)
    if not isinstance(node, Mapping):
        return ()
    inputs = node.get("inputs", {})
    if not isinstance(inputs, Mapping):
        return ()
    upstream: list[str] = []
    for input_value in inputs.values():
        link_source = link_source_node_id(input_value)
        if link_source is None:
            continue
        upstream.append(link_source)
        upstream.extend(
            _upstream_node_ids(
                workflow_payload=workflow_payload,
                start_node_id=link_source,
                visited=visited,
            )
        )
    return tuple(upstream)


def downstream_node_ids(
    *,
    workflow_payload: Mapping[str, JsonValue],
    start_node_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Return downstream node ids reachable from linked outputs."""

    workflow_nodes = executable_prompt_nodes(workflow_payload)
    reverse_links: dict[str, list[str]] = {}
    for node_id, node in workflow_nodes.items():
        if not isinstance(node, Mapping):
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, Mapping):
            continue
        for input_value in inputs.values():
            link_source = link_source_node_id(input_value)
            if link_source is not None:
                reverse_links.setdefault(link_source, []).append(str(node_id))

    visited = set(start_node_ids)
    pending = list(start_node_ids)
    downstream: list[str] = []
    while pending:
        current = pending.pop(0)
        for next_node_id in reverse_links.get(current, ()):
            if next_node_id in visited:
                continue
            visited.add(next_node_id)
            downstream.append(next_node_id)
            pending.append(next_node_id)
    return tuple(downstream)


def link_source_node_id(input_value: object) -> str | None:
    """Return the source node id from one Comfy link input."""

    if (
        isinstance(input_value, list)
        and len(input_value) == 2
        and isinstance(input_value[0], str)
        and isinstance(input_value[1], int)
    ):
        return input_value[0]
    return None


def node_title(node: Mapping[str, JsonValue]) -> str:
    """Return one compiled node's Sugar title metadata."""

    metadata = node.get("_meta", {})
    if not isinstance(metadata, Mapping):
        return ""
    title = metadata.get("title")
    return title if isinstance(title, str) else ""


__all__ = [
    "downstream_node_ids",
    "link_source_node_id",
    "node_title",
    "prompt_node_ids",
    "upstream_node_ids",
]
