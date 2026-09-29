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

"""Inventory concrete node classes persisted inside Comfy subgraphs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence


def subgraph_body_node_classes(subgraph: Mapping[str, object]) -> tuple[str, ...]:
    """Return every normalized node class persisted by one subgraph body."""

    nodes = subgraph.get("nodes")
    node_entries: Iterable[object]
    if isinstance(nodes, Mapping):
        node_entries = nodes.values()
    elif isinstance(nodes, Sequence) and not isinstance(nodes, (str, bytes)):
        node_entries = nodes
    else:
        return ()
    classes: set[str] = set()
    for node in node_entries:
        if not isinstance(node, Mapping):
            continue
        class_type = node.get("type")
        if isinstance(class_type, str) and (normalized := class_type.strip()):
            classes.add(normalized)
    return tuple(sorted(classes))


__all__ = ["subgraph_body_node_classes"]
