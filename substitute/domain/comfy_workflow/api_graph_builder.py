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

"""Build executable Comfy API graphs from editable direct-workflow buffers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy

from substitute.domain.common import JsonObject

from .editor_definitions import workflow_node_execution_role
from .node_roles import WorkflowNodeExecutionRole

_OMIT_INPUT = object()


class ComfyApiGraphBuildError(ValueError):
    """Report a direct workflow graph that cannot be made executable."""


class ComfyApiGraphBuilder:
    """Strip editor metadata and apply Comfy disabled and bypass node modes."""

    def build(self, buffer: Mapping[str, object]) -> JsonObject:
        """Return a detached executable API graph from an editor buffer."""

        raw_nodes = buffer.get("nodes")
        if not isinstance(raw_nodes, Mapping):
            raise ComfyApiGraphBuildError("Direct workflow buffer has no node graph.")
        nodes = {
            str(node_id): node
            for node_id, node in raw_nodes.items()
            if isinstance(node, Mapping)
        }
        executable: dict[str, object] = {}
        for node_id, node in nodes.items():
            role = workflow_node_execution_role(node)
            if role in {
                WorkflowNodeExecutionRole.VALUE_PROXY.value,
                WorkflowNodeExecutionRole.ROUTING.value,
                WorkflowNodeExecutionRole.ANNOTATION.value,
            }:
                continue
            if role == WorkflowNodeExecutionRole.UNRESOLVED.value:
                raise ComfyApiGraphBuildError(
                    f"Direct workflow node {node_id!r} has unresolved execution semantics."
                )
            if _node_mode(node) in {2, 4}:
                continue
            class_type = node.get("class_type")
            inputs = node.get("inputs")
            if not isinstance(class_type, str) or not isinstance(inputs, Mapping):
                raise ComfyApiGraphBuildError(
                    f"Direct workflow node {node_id!r} is missing class_type or inputs."
                )
            executable_inputs: dict[str, object] = {}
            for input_name, value in inputs.items():
                resolved_value = self._resolve_input_value(
                    deepcopy(value),
                    nodes=nodes,
                    trail=(node_id,),
                )
                if resolved_value is not _OMIT_INPUT:
                    executable_inputs[str(input_name)] = resolved_value
            payload: dict[str, object] = {
                "class_type": class_type,
                "inputs": executable_inputs,
            }
            meta = node.get("_meta")
            if isinstance(meta, Mapping):
                payload["_meta"] = {
                    str(key): deepcopy(value) for key, value in meta.items()
                }
            executable[node_id] = payload
        if not executable:
            raise ComfyApiGraphBuildError(
                "Direct workflow has no active executable nodes."
            )
        return executable

    def _resolve_input_value(
        self,
        value: object,
        *,
        nodes: Mapping[str, Mapping[str, object]],
        trail: tuple[str, ...],
    ) -> object:
        """Resolve one input link through any bypassed upstream nodes."""

        link = _node_link(value)
        if link is None:
            return value
        source_id, source_slot = link
        source = nodes.get(source_id)
        if source is None:
            raise ComfyApiGraphBuildError(
                f"Workflow input references missing node {source_id!r}."
            )
        role = workflow_node_execution_role(source)
        if role == WorkflowNodeExecutionRole.VALUE_PROXY.value:
            return _value_proxy_literal(source, node_id=source_id)
        if role == WorkflowNodeExecutionRole.UNRESOLVED.value:
            raise ComfyApiGraphBuildError(
                f"Workflow input depends on unresolved node {source_id!r}."
            )
        mode = _node_mode(source)
        if mode == 2:
            raise ComfyApiGraphBuildError(
                f"Active workflow input depends on disabled node {source_id!r}."
            )
        if mode != 4:
            return [source_id, source_slot]
        if source_id in trail:
            raise ComfyApiGraphBuildError("Workflow bypass links contain a cycle.")
        passthrough = _bypass_input_link(source, source_slot)
        if passthrough is None:
            return _OMIT_INPUT
        return self._resolve_input_value(
            passthrough,
            nodes=nodes,
            trail=(*trail, source_id),
        )


def _node_mode(node: Mapping[str, object]) -> int:
    """Return one node's serialized Comfy execution mode."""

    mode = node.get("mode", 0)
    return mode if isinstance(mode, int) and not isinstance(mode, bool) else 0


def _node_link(value: object) -> tuple[str, int] | None:
    """Return a canonical API link pair from a JSON-like value."""

    if (
        isinstance(value, Sequence)
        and not isinstance(value, str | bytes)
        and len(value) >= 2
        and isinstance(value[0], str | int)
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)
    ):
        return str(value[0]), value[1]
    return None


def _bypass_input_link(
    node: Mapping[str, object],
    output_slot: int,
) -> object | None:
    """Return the linked input Comfy can route through one bypassed output."""

    workflow_metadata = node.get("_workflow")
    if not isinstance(workflow_metadata, Mapping):
        return None
    inputs = workflow_metadata.get("inputs")
    outputs = workflow_metadata.get("outputs")
    node_inputs = node.get("inputs")
    if not isinstance(inputs, Sequence) or isinstance(inputs, str | bytes):
        return None
    if not isinstance(outputs, Sequence) or isinstance(outputs, str | bytes):
        return None
    if not isinstance(node_inputs, Mapping) or output_slot >= len(outputs):
        return None
    output = outputs[output_slot]
    output_type = str(output.get("type", "")) if isinstance(output, Mapping) else ""
    candidates: list[object] = []
    for input_metadata in inputs:
        if not isinstance(input_metadata, Mapping):
            continue
        input_name = input_metadata.get("name")
        input_type = str(input_metadata.get("type", ""))
        if not isinstance(input_name, str) or input_type != output_type:
            continue
        value = node_inputs.get(input_name)
        if _node_link(value) is not None:
            candidates.append(value)
    if output_slot < len(candidates):
        return candidates[output_slot]
    return candidates[0] if candidates else None


def _value_proxy_literal(node: Mapping[str, object], *, node_id: str) -> object:
    """Return the current literal stored by one frontend value-proxy node."""

    workflow_metadata = node.get("_workflow")
    inputs = node.get("inputs")
    if not isinstance(workflow_metadata, Mapping) or not isinstance(inputs, Mapping):
        raise ComfyApiGraphBuildError(
            f"Value-proxy node {node_id!r} has no editable field metadata."
        )
    field_key = workflow_metadata.get("value_field")
    if not isinstance(field_key, str) or field_key not in inputs:
        raise ComfyApiGraphBuildError(
            f"Value-proxy node {node_id!r} has no current literal value."
        )
    return deepcopy(inputs[field_key])


__all__ = ["ComfyApiGraphBuildError", "ComfyApiGraphBuilder"]
