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

"""Resolve authored top-level fields exposed by native Comfy subgraphs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeGuard


def widget_backed_subgraph_fields(
    graph: Mapping[str, object],
) -> tuple[tuple[str, str], ...]:
    """Return wrapper inputs backed by editable widgets inside each subgraph."""

    authored_inputs_by_class = _authored_inputs_by_subgraph_class(
        graph.get("subgraphs")
    )
    nodes = graph.get("nodes")
    if not isinstance(nodes, Mapping):
        return ()

    fields: list[tuple[str, str]] = []
    for node_key, node in nodes.items():
        if not isinstance(node_key, str) or not isinstance(node, Mapping):
            continue
        class_type = node.get("class_type")
        if not isinstance(class_type, str):
            continue
        fields.extend(
            (node_key, input_name)
            for input_name in authored_inputs_by_class.get(class_type, ())
        )
    return tuple(fields)


def _authored_inputs_by_subgraph_class(
    raw_subgraphs: object,
) -> dict[str, tuple[str, ...]]:
    """Index editable public input names by native subgraph class identifier."""

    if not _is_sequence(raw_subgraphs):
        return {}
    indexed: dict[str, tuple[str, ...]] = {}
    for subgraph in raw_subgraphs:
        if not isinstance(subgraph, Mapping):
            continue
        subgraph_id = subgraph.get("id")
        if not isinstance(subgraph_id, str) or not subgraph_id:
            continue
        widget_link_ids = _widget_link_ids(subgraph.get("nodes"))
        indexed[subgraph_id] = _public_inputs_for_widget_links(
            subgraph.get("inputs"),
            widget_link_ids,
        )
    return indexed


def _widget_link_ids(raw_nodes: object) -> frozenset[object]:
    """Return links whose internal targets expose Comfy widget metadata."""

    if not _is_sequence(raw_nodes):
        return frozenset()
    link_ids: set[object] = set()
    for node in raw_nodes:
        if not isinstance(node, Mapping):
            continue
        inputs = node.get("inputs")
        if not _is_sequence(inputs):
            continue
        for input_spec in inputs:
            if not isinstance(input_spec, Mapping) or "widget" not in input_spec:
                continue
            link_id = input_spec.get("link")
            if isinstance(link_id, (str, int)):
                link_ids.add(link_id)
    return frozenset(link_ids)


def _public_inputs_for_widget_links(
    raw_inputs: object,
    widget_link_ids: frozenset[object],
) -> tuple[str, ...]:
    """Return public input names connected to at least one editable widget."""

    if not _is_sequence(raw_inputs):
        return ()
    names: list[str] = []
    for input_spec in raw_inputs:
        if not isinstance(input_spec, Mapping):
            continue
        name = input_spec.get("name")
        link_ids = input_spec.get("linkIds")
        if not isinstance(name, str) or not name or not _is_sequence(link_ids):
            continue
        if any(link_id in widget_link_ids for link_id in link_ids):
            names.append(name)
    return tuple(names)


def _is_sequence(value: object) -> TypeGuard[Sequence[object]]:
    """Return whether a dynamic value is a non-text sequence."""

    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


__all__ = ["widget_backed_subgraph_fields"]
