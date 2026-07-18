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

"""Convert Comfy LiteGraph workflow documents into editable API-shaped graphs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass

from substitute.domain.common import JsonObject

from .editor_definitions import (
    editor_definition_from_comfy_definition,
    editor_definition_for_value_proxy,
    editor_definition_for_widget_inputs,
)
from .links import WorkflowLinkIndex
from .node_roles import WorkflowNodeExecutionRole, known_execution_role
from .widget_values import node_widget_values, proxy_widget_values

NodeLinkValue = list[object]
ResolvedInputValue = object
_UNRESOLVED_INTERFACE = object()
_NON_PROJECTED_ROLES = frozenset(
    {
        WorkflowNodeExecutionRole.ANNOTATION,
        WorkflowNodeExecutionRole.ROUTING,
    }
)


class ComfyWorkflowConversionError(ValueError):
    """Report a malformed or unsupported Comfy workflow document."""


@dataclass(frozen=True, slots=True)
class _GraphScope:
    """Carry one root or subgraph LiteGraph scope during expansion."""

    nodes: tuple[Mapping[str, object], ...]
    links: WorkflowLinkIndex
    namespace: str
    interface_values: Mapping[int, ResolvedInputValue]
    proxy_overrides: Mapping[tuple[str, str], object]
    title_prefix: str


class ComfyWorkflowConverter:
    """Compile Comfy UI workflows through one isolated conversion session."""

    def convert(
        self,
        workflow: Mapping[str, object],
        *,
        node_definitions: Mapping[str, Mapping[str, object]] | None = None,
    ) -> JsonObject:
        """Return an editable intermediate graph from one UI workflow document."""

        return _ComfyWorkflowConversionSession(
            node_definitions=node_definitions or {},
        ).convert(workflow)


class _ComfyWorkflowConversionSession:
    """Own mutable traversal state for one isolated workflow compilation."""

    def __init__(
        self,
        *,
        node_definitions: Mapping[str, Mapping[str, object]],
    ) -> None:
        """Store live definitions used to decode positional widgets."""

        self._node_definitions = node_definitions
        self._definitions: dict[str, Mapping[str, object]] = {}
        self._expanded_nodes: dict[str, object] = {}

    def convert(self, workflow: Mapping[str, object]) -> JsonObject:
        """Compile one UI workflow into the shared editable graph contract."""

        try:
            root_nodes = _node_records(workflow.get("nodes"))
            definitions = _subgraph_definitions(workflow.get("definitions"))
            self._definitions = definitions
            scope = _GraphScope(
                nodes=root_nodes,
                links=WorkflowLinkIndex(workflow.get("links", ())),
                namespace="",
                interface_values={},
                proxy_overrides={},
                title_prefix="",
            )
            self._expand_scope(scope)
        except (KeyError, TypeError, ValueError) as error:
            raise ComfyWorkflowConversionError(str(error)) from error
        if not self._expanded_nodes:
            raise ComfyWorkflowConversionError(
                "Comfy workflow does not contain executable nodes."
            )
        return {"nodes": self._expanded_nodes}

    def _expand_scope(self, scope: _GraphScope) -> dict[int, ResolvedInputValue]:
        """Expand a graph scope and return its interface output sources."""

        nodes_by_id = {str(node["id"]): node for node in scope.nodes}
        subgraph_outputs: dict[str, dict[int, ResolvedInputValue]] = {}
        expanding: set[str] = set()

        def expand_subgraph(
            origin_id: str,
            origin: Mapping[str, object],
            definition: Mapping[str, object],
        ) -> dict[int, ResolvedInputValue]:
            """Expand one subgraph instance once within this graph scope."""

            if origin_id in expanding:
                raise ValueError(
                    "Recursive Comfy subgraph definitions are unsupported."
                )
            if origin_id not in subgraph_outputs:
                expanding.add(origin_id)
                try:
                    subgraph_outputs[origin_id] = self._expand_subgraph_instance(
                        outer_scope=scope,
                        outer_node=origin,
                        definition=definition,
                        source_for=source_for,
                    )
                finally:
                    expanding.remove(origin_id)
            return subgraph_outputs[origin_id]

        def source_for(origin_id: str, origin_slot: int) -> ResolvedInputValue:
            """Resolve a link source through standard or subgraph nodes."""

            if origin_id == "-10":
                supplied_value = scope.interface_values.get(
                    origin_slot,
                    _UNRESOLVED_INTERFACE,
                )
                if supplied_value is _UNRESOLVED_INTERFACE:
                    return _UNRESOLVED_INTERFACE
                return deepcopy(supplied_value)
            origin = nodes_by_id.get(origin_id)
            if origin is None:
                raise ValueError(
                    f"Workflow link references unknown node {origin_id!r}."
                )
            origin_type = str(origin.get("type", ""))
            if origin_type == "Reroute":
                reroute_inputs = _input_records(origin.get("inputs"))
                if not reroute_inputs:
                    return _UNRESOLVED_INTERFACE
                link_id = reroute_inputs[0].get("link")
                link = scope.links.by_id(link_id) if link_id is not None else None
                if link is None:
                    return _UNRESOLVED_INTERFACE
                return source_for(link.origin_id, link.origin_slot)
            definition = self._definitions.get(origin_type)
            if definition is None:
                return [_qualified_id(scope.namespace, origin_id), origin_slot]
            outputs = expand_subgraph(origin_id, origin, definition)
            if origin_slot not in outputs:
                raise ValueError(
                    f"Subgraph node {origin_id!r} has no output slot {origin_slot}."
                )
            return deepcopy(outputs[origin_slot])

        for node in scope.nodes:
            node_id = str(node["id"])
            definition = self._definitions.get(str(node.get("type", "")))
            if definition is not None:
                expand_subgraph(node_id, node, definition)
                continue
            self._append_standard_node(
                scope=scope,
                node=node,
                source_for=source_for,
            )

        outputs: dict[int, ResolvedInputValue] = {}
        for output_slot in _interface_slot_indexes(scope, output=True):
            link = scope.links.into_target("-20", output_slot)
            if link is not None:
                resolved = source_for(link.origin_id, link.origin_slot)
                if resolved is not _UNRESOLVED_INTERFACE:
                    outputs[output_slot] = resolved
        return outputs

    def _expand_subgraph_instance(
        self,
        *,
        outer_scope: _GraphScope,
        outer_node: Mapping[str, object],
        definition: Mapping[str, object],
        source_for: object,
    ) -> dict[int, ResolvedInputValue]:
        """Expand one UUID-typed subgraph node into namespaced internal nodes."""

        if not callable(source_for):
            raise TypeError("Subgraph source resolver is not callable.")
        interface_widgets, internal_overrides = proxy_widget_values(outer_node)
        outer_inputs = _input_records(outer_node.get("inputs"))
        definition_inputs = _interface_records(definition.get("inputs"))
        interface_values: dict[int, ResolvedInputValue] = {}
        for slot, definition_input in enumerate(definition_inputs):
            input_name = str(definition_input.get("name", slot))
            outer_input = _input_by_name_or_slot(outer_inputs, input_name, slot)
            link = (
                outer_scope.links.by_id(outer_input.get("link"))
                if outer_input is not None and outer_input.get("link") is not None
                else None
            )
            if link is not None:
                interface_values[slot] = source_for(link.origin_id, link.origin_slot)
            elif input_name in interface_widgets:
                interface_values[slot] = deepcopy(interface_widgets[input_name])

        outer_id = str(outer_node["id"])
        outer_title = _subgraph_title(outer_node, definition)
        namespace = _qualified_id(outer_scope.namespace, outer_id)
        nested_scope = _GraphScope(
            nodes=_node_records(definition.get("nodes")),
            links=WorkflowLinkIndex(definition.get("links", ())),
            namespace=namespace,
            interface_values=interface_values,
            proxy_overrides=internal_overrides,
            title_prefix=_joined_title(outer_scope.title_prefix, outer_title),
        )
        return self._expand_scope(nested_scope)

    def _append_standard_node(
        self,
        *,
        scope: _GraphScope,
        node: Mapping[str, object],
        source_for: object,
    ) -> None:
        """Append one executable node with resolved links and widget values."""

        if not callable(source_for):
            raise TypeError("Node source resolver is not callable.")
        class_type = str(node.get("type", "")).strip()
        execution_role = known_execution_role(class_type)
        if not class_type or execution_role in _NON_PROJECTED_ROLES:
            return
        node_id = str(node["id"])
        qualified_id = _qualified_id(scope.namespace, node_id)
        if execution_role is WorkflowNodeExecutionRole.VALUE_PROXY:
            self._append_value_proxy_node(
                scope=scope,
                node=node,
                qualified_id=qualified_id,
            )
            return
        node_definition = self._node_definitions.get(class_type)
        widget_values = node_widget_values(node, node_definition)
        inputs: dict[str, object] = {}
        input_metadata: list[dict[str, object]] = []
        for slot, input_record in enumerate(_input_records(node.get("inputs"))):
            input_name = str(input_record.get("name", slot))
            input_type = str(input_record.get("type", ""))
            input_metadata.append({"name": input_name, "type": input_type})
            link_id = input_record.get("link")
            link = scope.links.by_id(link_id) if link_id is not None else None
            if link is not None:
                resolved = source_for(link.origin_id, link.origin_slot)
                if resolved is not _UNRESOLVED_INTERFACE:
                    inputs[input_name] = resolved
                    continue
            proxy_key = (node_id, input_name)
            if proxy_key in scope.proxy_overrides:
                inputs[input_name] = deepcopy(scope.proxy_overrides[proxy_key])
            elif input_name in widget_values:
                inputs[input_name] = deepcopy(widget_values[input_name])
        for field_key, value in widget_values.items():
            inputs.setdefault(field_key, deepcopy(value))
        title = _joined_title(scope.title_prefix, _node_title(node))
        workflow_metadata: dict[str, object] = {
            "inputs": input_metadata,
            "outputs": _output_metadata(node.get("outputs")),
            "execution_role": WorkflowNodeExecutionRole.EXECUTABLE.value,
        }
        editor_definition = editor_definition_from_comfy_definition(
            node_definition,
            widget_values,
        ) or editor_definition_for_widget_inputs(node.get("inputs"), widget_values)
        workflow_metadata["editor_definition"] = editor_definition
        self._expanded_nodes[qualified_id] = {
            "class_type": class_type,
            "inputs": inputs,
            "mode": _node_mode(node),
            "_meta": {"title": title},
            "_workflow": workflow_metadata,
        }

    def _append_value_proxy_node(
        self,
        *,
        scope: _GraphScope,
        node: Mapping[str, object],
        qualified_id: str,
    ) -> None:
        """Append one frontend value proxy as a regular one-field editor node."""

        field_key, value, editor_definition = editor_definition_for_value_proxy(node)
        self._expanded_nodes[qualified_id] = {
            "class_type": str(node.get("type", "")).strip(),
            "inputs": {field_key: value},
            "mode": _node_mode(node),
            "_meta": {
                "title": _joined_title(scope.title_prefix, _node_title(node)),
            },
            "_workflow": {
                "inputs": [],
                "outputs": _output_metadata(node.get("outputs")),
                "execution_role": WorkflowNodeExecutionRole.VALUE_PROXY.value,
                "editor_definition": editor_definition,
                "value_field": field_key,
            },
        }


def _node_records(payload: object) -> tuple[Mapping[str, object], ...]:
    """Return validated LiteGraph node records."""

    if not isinstance(payload, Sequence) or isinstance(payload, str | bytes):
        raise ValueError("Comfy workflow nodes must be an array.")
    nodes: list[Mapping[str, object]] = []
    for node in payload:
        if not isinstance(node, Mapping) or "id" not in node:
            raise ValueError("Every Comfy workflow node must be an object with an id.")
        nodes.append(node)
    return tuple(nodes)


def _subgraph_definitions(payload: object) -> dict[str, Mapping[str, object]]:
    """Return subgraph definitions indexed by UUID type."""

    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError("Comfy workflow definitions must be an object.")
    subgraphs = payload.get("subgraphs", ())
    if not isinstance(subgraphs, Sequence) or isinstance(subgraphs, str | bytes):
        raise ValueError("Comfy workflow subgraph definitions must be an array.")
    result: dict[str, Mapping[str, object]] = {}
    for definition in subgraphs:
        if not isinstance(definition, Mapping) or not isinstance(
            definition.get("id"), str
        ):
            raise ValueError("Every Comfy subgraph definition must have a string id.")
        result[str(definition["id"])] = definition
    return result


def _input_records(payload: object) -> tuple[Mapping[str, object], ...]:
    """Return node input records, tolerating nodes without inputs."""

    if payload is None:
        return ()
    if not isinstance(payload, Sequence) or isinstance(payload, str | bytes):
        raise ValueError("Comfy node inputs must be an array.")
    return tuple(item for item in payload if isinstance(item, Mapping))


def _interface_records(payload: object) -> tuple[Mapping[str, object], ...]:
    """Return validated subgraph interface records."""

    if payload is None:
        return ()
    if not isinstance(payload, Sequence) or isinstance(payload, str | bytes):
        raise ValueError("Comfy subgraph interfaces must be arrays.")
    return tuple(item for item in payload if isinstance(item, Mapping))


def _input_by_name_or_slot(
    inputs: tuple[Mapping[str, object], ...],
    name: str,
    slot: int,
) -> Mapping[str, object] | None:
    """Return an outer subgraph input by stable name with slot fallback."""

    for input_record in inputs:
        if input_record.get("name") == name:
            return input_record
    return inputs[slot] if slot < len(inputs) else None


def _qualified_id(namespace: str, node_id: str) -> str:
    """Return a stable API node id for one nested graph node."""

    return f"{namespace}:{node_id}" if namespace else node_id


def _node_title(node: Mapping[str, object]) -> str:
    """Return the author-facing node title with class fallback."""

    title = node.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    properties = node.get("properties")
    if isinstance(properties, Mapping):
        search_name = properties.get("Node name for S&R")
        if isinstance(search_name, str) and search_name.strip():
            return search_name.strip()
    return str(node.get("type", node.get("id", "Node")))


def _subgraph_title(
    outer_node: Mapping[str, object],
    definition: Mapping[str, object],
) -> str:
    """Return a readable subgraph instance title with definition fallback."""

    explicit_title = outer_node.get("title")
    if isinstance(explicit_title, str) and explicit_title.strip():
        return explicit_title.strip()
    definition_name = definition.get("name")
    if isinstance(definition_name, str) and definition_name.strip():
        return definition_name.removeprefix("local-").strip()
    return _node_title(outer_node)


def _joined_title(prefix: str, title: str) -> str:
    """Join nested subgraph titles without exposing synthetic ids."""

    return f"{prefix} / {title}" if prefix else title


def _node_mode(node: Mapping[str, object]) -> int:
    """Return a supported serialized Comfy execution mode."""

    mode = node.get("mode", 0)
    return mode if isinstance(mode, int) and not isinstance(mode, bool) else 0


def _output_metadata(payload: object) -> list[dict[str, object]]:
    """Return the output type metadata needed for bypass rewiring."""

    if not isinstance(payload, Sequence) or isinstance(payload, str | bytes):
        return []
    result: list[dict[str, object]] = []
    for slot, output in enumerate(payload):
        if not isinstance(output, Mapping):
            result.append({"slot": slot, "type": ""})
            continue
        result.append(
            {
                "slot": slot,
                "name": str(output.get("name", slot)),
                "type": str(output.get("type", "")),
            }
        )
    return result


def _interface_slot_indexes(scope: _GraphScope, *, output: bool) -> tuple[int, ...]:
    """Return virtual interface slots observed in one graph scope's links."""

    target_id = "-20" if output else "-10"
    return scope.links.target_slots(target_id)


__all__ = ["ComfyWorkflowConversionError", "ComfyWorkflowConverter"]
