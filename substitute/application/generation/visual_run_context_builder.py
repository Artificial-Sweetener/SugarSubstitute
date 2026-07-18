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

"""Build explicit per-node visual routing metadata for one Comfy run."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.cubes import cube_alias_body
from substitute.application.ports.comfy_gateway import (
    ListenerOutputSource,
    QueueVisualRunContext,
)
from substitute.application.recipes.workflow_payload_nodes import (
    executable_prompt_nodes,
)
from substitute.domain.common import WorkflowId


class VisualRunContextBuilder:
    """Own visual source derivation for cube and direct workflow payloads."""

    def build(
        self,
        *,
        workflow_payload: dict[str, object],
        workflow_id: WorkflowId,
        generation_run_id: str,
        client_id: str,
        scene_run_id: str | None,
        scene_key: str | None,
        scene_title: str | None,
        scene_order: int | None,
        scene_count: int | None,
        explicit_sources: tuple[ListenerOutputSource, ...] = (),
    ) -> QueueVisualRunContext:
        """Return Backend routing metadata with explicit sources taking priority."""

        prompt_nodes = executable_prompt_nodes(workflow_payload)
        node_to_output_source = _node_to_cube_output_source(prompt_nodes, workflow_id)
        explicit_by_node = {
            source.node_id: {
                "sourceKey": source.source_key,
                "sourceLabel": source.source_label,
                "cubeAlias": source.source_label,
            }
            for source in explicit_sources
        }
        sources: dict[str, dict[str, str]] = {}
        for node_id, node_data in prompt_nodes.items():
            if not isinstance(node_data, dict):
                continue
            source = explicit_by_node.get(node_id) or node_to_output_source.get(node_id)
            if source is None:
                label = _source_label_for_prompt_node(node_id, node_data)
                source = {
                    "sourceKey": f"{workflow_id}:{node_id}",
                    "sourceLabel": label,
                    "cubeAlias": label,
                }
            sources[node_id] = source
        if not sources:
            raise RuntimeError("Generation visual routing context has no source nodes.")
        return QueueVisualRunContext(
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            client_id=client_id,
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            scene_title=scene_title,
            scene_order=scene_order,
            scene_count=scene_count,
            sources=sources,
        )


def _source_label_for_prompt_node(node_id: str, node_data: dict[str, object]) -> str:
    """Return the Substitute source label for one executable prompt node."""

    meta = node_data.get("_meta")
    meta_title = ""
    if isinstance(meta, dict):
        title = meta.get("title")
        if isinstance(title, str):
            meta_title = title
    cube_alias = meta_title.split(".", 1)[0] if "." in meta_title else meta_title
    return cube_alias_body(cube_alias) or node_id


def _node_to_cube_output_source(
    prompt_nodes: Mapping[str, object],
    workflow_id: WorkflowId,
) -> dict[str, dict[str, str]]:
    """Map upstream executable nodes to their unambiguous cube-output source."""

    output_sources: dict[str, dict[str, str]] = {}
    candidate_sources_by_node: dict[str, list[dict[str, str]]] = {}
    for node_id, node_data in prompt_nodes.items():
        if not isinstance(node_data, dict):
            continue
        if node_data.get("class_type") != "SugarCubes.CubeOutput":
            continue
        label = _source_label_for_prompt_node(node_id, node_data)
        source = {
            "sourceKey": f"{workflow_id}:{node_id}",
            "sourceLabel": label,
            "cubeAlias": label,
        }
        output_sources[node_id] = source
        for upstream_node_id in _upstream_node_ids(prompt_nodes, node_id):
            candidate_sources_by_node.setdefault(upstream_node_id, []).append(source)
    for node_id, source in output_sources.items():
        candidate_sources_by_node[node_id] = [source]
    return {
        node_id: sources[0]
        for node_id, sources in candidate_sources_by_node.items()
        if len({source["sourceKey"] for source in sources}) == 1
    }


def _upstream_node_ids(
    prompt_nodes: Mapping[str, object],
    start_node_id: str,
) -> set[str]:
    """Return executable node ids that feed one output node."""

    visited: set[str] = set()
    pending = [start_node_id]
    while pending:
        node_id = pending.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        node_data = prompt_nodes.get(node_id)
        if not isinstance(node_data, dict):
            continue
        inputs = node_data.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        for upstream_node_id in _linked_node_ids(inputs.values()):
            if upstream_node_id not in visited:
                pending.append(upstream_node_id)
    return visited


def _linked_node_ids(values: object) -> tuple[str, ...]:
    """Return Comfy link source node ids nested in input values."""

    if isinstance(values, Mapping):
        iterable: tuple[object, ...] = tuple(values.values())
    elif isinstance(values, list | tuple):
        iterable = tuple(values)
    else:
        return ()
    linked: list[str] = []
    for value in iterable:
        if (
            isinstance(value, list | tuple)
            and len(value) >= 2
            and isinstance(value[0], str | int)
            and isinstance(value[1], int)
        ):
            linked.append(str(value[0]))
        elif isinstance(value, Mapping):
            linked.extend(_linked_node_ids(tuple(value.values())))
        elif isinstance(value, list | tuple):
            linked.extend(_linked_node_ids(value))
    return tuple(linked)


__all__ = ["VisualRunContextBuilder"]
