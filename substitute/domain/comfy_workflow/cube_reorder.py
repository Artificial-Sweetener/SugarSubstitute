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

"""Apply a SugarCubes-authorized Cube segment reorder to local graph geometry."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import replace
from math import isfinite

from substitute.domain.common import JsonObject

from .cube_analysis import (
    CanonicalCubeGraphAnalysis,
    CubeGraphEdgeOrigin,
)

_MINIMUM_GAP = 24.0


def apply_cached_cube_reorder(
    analysis: CanonicalCubeGraphAnalysis,
    *,
    segment_instance_ids: Sequence[str],
    ordered_instance_ids: Sequence[str],
) -> CanonicalCubeGraphAnalysis:
    """Apply one previously authorized segment permutation without target IO."""

    current = tuple(segment_instance_ids)
    requested = tuple(ordered_instance_ids)
    segment = next(
        (
            candidate
            for candidate in analysis.segments
            if candidate.instance_ids == current
        ),
        None,
    )
    if segment is None:
        raise ValueError("Cube graph segment is unavailable.")
    if not segment.reorderable:
        raise ValueError("Fixed Cube graph segments cannot be reordered.")
    if len(requested) != len(set(requested)) or set(requested) != set(current):
        raise ValueError("Cube reorder must be an exact segment permutation.")

    graph = deepcopy(analysis.workflow)
    nodes = _nodes_by_id(graph)
    node_ids = {
        instance.instance_id: instance.node_id for instance in analysis.instances
    }
    current_nodes = [nodes[node_ids[instance_id]] for instance_id in current]
    requested_nodes = [nodes[node_ids[instance_id]] for instance_id in requested]
    positions = [_pair(node.get("pos"), "position") for node in current_nodes]
    widths = [max(0.0, _pair(node.get("size"), "size")[0]) for node in current_nodes]
    gaps = [
        max(_MINIMUM_GAP, positions[index + 1][0] - positions[index][0] - widths[index])
        for index in range(len(current_nodes) - 1)
    ]
    next_left = positions[0][0]
    for index, node in enumerate(requested_nodes):
        node["pos"] = [next_left, positions[index][1]]
        if index < len(gaps):
            node_width = max(0.0, _pair(node.get("size"), "size")[0])
            next_left += node_width + gaps[index]

    members = set(current)
    retained_edges = tuple(
        edge
        for edge in analysis.edges
        if edge.origin is CubeGraphEdgeOrigin.EXPLICIT
        or edge.source_instance_id not in members
        or edge.target_instance_id not in members
    )
    return replace(
        analysis,
        workflow_semantic_hash="",
        edges=retained_edges,
        proximity_edges=tuple(
            edge
            for edge in analysis.proximity_edges
            if edge.source_instance_id not in members
            or edge.target_instance_id not in members
        ),
        segments=tuple(
            replace(candidate, instance_ids=requested)
            if candidate is segment
            else candidate
            for candidate in analysis.segments
        ),
        workflow=graph,
    )


def _nodes_by_id(graph: JsonObject) -> dict[str, dict[str, object]]:
    """Index mutable serialized graph nodes by their normalized identity."""

    values = graph.get("nodes")
    if not isinstance(values, list):
        raise ValueError("Canonical Cube graph nodes are unavailable.")
    return {
        str(node["id"]): node
        for node in values
        if isinstance(node, dict)
        and "id" in node
        and not isinstance(node["id"], bool)
        and isinstance(node["id"], str | int)
    }


def _pair(value: object, label: str) -> tuple[float, float]:
    """Read one finite graph geometry pair required by local mutation."""

    if (
        not isinstance(value, Sequence)
        or isinstance(value, str | bytes | bytearray)
        or len(value) < 2
    ):
        raise ValueError(f"Cube {label} is unavailable.")
    first, second = value[0], value[1]
    if (
        isinstance(first, bool)
        or not isinstance(first, int | float)
        or isinstance(second, bool)
        or not isinstance(second, int | float)
        or not isfinite(float(first))
        or not isfinite(float(second))
    ):
        raise ValueError(f"Cube {label} must contain finite numbers.")
    return float(first), float(second)


__all__ = ["apply_cached_cube_reorder"]
