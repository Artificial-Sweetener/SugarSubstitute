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

"""Define stable output-source identity across repeated workflow runs."""

from __future__ import annotations


def output_source_key_for_node(node_id: str) -> str:
    """Return a workflow-local source key that survives generation reruns."""

    normalized_node_id = node_id.strip()
    if not normalized_node_id:
        raise ValueError("Output source node id cannot be empty.")
    return f"node:{normalized_node_id}"


def output_source_key_for_cube(*, cube_alias: str, node_id: str) -> str:
    """Return stable cube identity with node identity as an unlabeled fallback."""

    normalized_alias = cube_alias.strip()
    if normalized_alias:
        return f"cube:{normalized_alias}"
    return output_source_key_for_node(node_id)


def canonical_output_source_key(
    *,
    source_key: str,
    source_label: str,
    node_id: str,
) -> str:
    """Migrate a legacy run-scoped node key without altering explicit keys."""

    normalized_node_id = node_id.strip()
    if not normalized_node_id:
        return source_key
    stable_key = output_source_key_for_cube(
        cube_alias=source_label,
        node_id=normalized_node_id,
    )
    if source_key.startswith("cube:") or source_key == stable_key:
        return source_key
    if source_key.endswith(f":{normalized_node_id}"):
        return stable_key
    return source_key or stable_key


__all__ = [
    "canonical_output_source_key",
    "output_source_key_for_cube",
    "output_source_key_for_node",
]
