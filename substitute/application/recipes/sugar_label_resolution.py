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

"""Resolve SugarScript-visible labels against current SugarCube definitions."""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence, cast

from substitute.domain.common import (
    GlobalOverrideMap,
    GlobalOverrideSelectionMap,
    JsonObject,
    JsonValue,
)
from substitute.domain.cubes import is_subgraph_wrapper_class_type
from substitute.domain.recipes import ParsedSugarScript
from substitute.domain.recipes.sugar_path_codec import SugarPathCodec


_PATH_CODEC = SugarPathCodec()


class SugarScriptLabelResolutionError(ValueError):
    """Raised when a SugarScript label cannot resolve to one machine key."""


@dataclass(frozen=True)
class _NodeLabels:
    """Store node and input label bindings for one runtime node."""

    node_key: str
    label: str
    input_labels_by_key: Mapping[str, str]
    input_keys_by_label: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class _AliasLabels:
    """Store all script-addressable labels for one cube alias."""

    alias: str
    nodes_by_key: Mapping[str, _NodeLabels]
    node_keys_by_label: Mapping[str, tuple[str, ...]]


class SugarScriptLabelIndex:
    """Map between user-visible SugarScript labels and machine graph keys."""

    def __init__(self, aliases: Mapping[str, _AliasLabels]) -> None:
        """Store immutable alias label maps."""

        self._aliases = dict(aliases)

    @classmethod
    def from_cube_graphs(
        cls,
        cube_graphs_by_alias: Mapping[str, Mapping[str, Any]],
    ) -> SugarScriptLabelIndex:
        """Build an index from materialized cube runtime graphs."""

        return cls(
            {
                alias: _build_alias_labels(alias=alias, graph=graph)
                for alias, graph in cube_graphs_by_alias.items()
            }
        )

    def node_label_for(self, alias: str, node_key: str) -> str:
        """Return the script-visible node label for one machine node key."""

        alias_labels = self._alias_labels(alias)
        node_labels = alias_labels.nodes_by_key.get(node_key)
        if node_labels is None:
            return node_key
        self._ensure_unique_node_label(alias_labels, node_labels.label)
        return node_labels.label

    def input_label_for(self, alias: str, node_key: str, input_key: str) -> str:
        """Return the script-visible input label for one machine input key."""

        node_labels = self._node_labels(alias, node_key)
        if node_labels is None:
            return input_key
        input_label = node_labels.input_labels_by_key.get(input_key)
        if input_label is None:
            return input_key
        self._ensure_unique_input_label(alias, node_labels, input_label)
        return input_label

    def global_input_label_for(
        self,
        input_key: str,
        participant_fields: Iterable[tuple[str, str, str]],
    ) -> str:
        """Return the wildcard label for one override machine key."""

        labels = {
            self.input_label_for(alias, node_key, field_key)
            for alias, node_key, field_key in participant_fields
            if field_key == input_key
        }
        if not labels:
            labels = self._labels_for_global_input_key(input_key)
        if len(labels) > 1:
            raise SugarScriptLabelResolutionError(
                "Global override input "
                f"'{input_key}' has multiple visible labels: {', '.join(sorted(labels))}."
            )
        return next(iter(labels), input_key)

    def endpoint_label_for(self, alias: str, endpoint_key: JsonValue) -> JsonValue:
        """Return the visible connect endpoint label for one machine endpoint."""

        if not isinstance(endpoint_key, str):
            return endpoint_key
        return self._public_endpoint_label(alias, endpoint_key)

    def node_key_for_label(self, alias: str, node_label: str) -> str:
        """Return the machine node key addressed by one script label."""

        alias_labels = self._alias_labels(alias)
        keys = alias_labels.node_keys_by_label.get(node_label, ())
        if len(keys) == 1:
            return keys[0]
        if len(keys) > 1:
            raise SugarScriptLabelResolutionError(
                f"Cube alias '{alias}' has ambiguous node label '{node_label}' "
                f"for machine nodes: {', '.join(keys)}."
            )
        if node_label in alias_labels.nodes_by_key:
            return node_label
        raise SugarScriptLabelResolutionError(
            f"Cube alias '{alias}' has no node label '{node_label}'."
        )

    def input_key_for_label(self, alias: str, node_key: str, input_label: str) -> str:
        """Return the machine input key addressed by one script label."""

        node_labels = self._node_labels(alias, node_key)
        if node_labels is None:
            return input_label
        keys = node_labels.input_keys_by_label.get(input_label, ())
        if len(keys) == 1:
            return keys[0]
        if len(keys) > 1:
            raise SugarScriptLabelResolutionError(
                f"Cube alias '{alias}' node '{node_key}' has ambiguous input label "
                f"'{input_label}' for machine inputs: {', '.join(keys)}."
            )
        if input_label in node_labels.input_labels_by_key:
            return input_label
        raise SugarScriptLabelResolutionError(
            f"Cube alias '{alias}' node '{node_key}' has no input label "
            f"'{input_label}'."
        )

    def global_input_key_for_label(self, input_label: str) -> str:
        """Return the wildcard machine key addressed by one script label."""

        keys: set[str] = set()
        for alias_labels in self._aliases.values():
            for node_labels in alias_labels.nodes_by_key.values():
                keys.update(node_labels.input_keys_by_label.get(input_label, ()))
        if len(keys) == 1:
            return next(iter(keys))
        if len(keys) > 1:
            raise SugarScriptLabelResolutionError(
                f"Global override label '{input_label}' maps to multiple machine "
                f"inputs: {', '.join(sorted(keys))}."
            )
        return input_label

    def _alias_labels(self, alias: str) -> _AliasLabels:
        """Return label mappings for one known alias."""

        alias_labels = self._aliases.get(alias)
        if alias_labels is None:
            raise SugarScriptLabelResolutionError(
                f"SugarScript references unknown cube alias '{alias}'."
            )
        return alias_labels

    def _node_labels(self, alias: str, node_key: str) -> _NodeLabels | None:
        """Return label mappings for one node, if known."""

        return self._alias_labels(alias).nodes_by_key.get(node_key)

    def _ensure_unique_node_label(
        self,
        alias_labels: _AliasLabels,
        node_label: str,
    ) -> None:
        """Fail when emission would produce an ambiguous node segment."""

        keys = alias_labels.node_keys_by_label.get(node_label, ())
        if len(keys) > 1:
            raise SugarScriptLabelResolutionError(
                f"Cube alias '{alias_labels.alias}' has duplicate node label "
                f"'{node_label}' for machine nodes: {', '.join(keys)}."
            )

    def _ensure_unique_input_label(
        self,
        alias: str,
        node_labels: _NodeLabels,
        input_label: str,
    ) -> None:
        """Fail when emission would produce an ambiguous input segment."""

        keys = node_labels.input_keys_by_label.get(input_label, ())
        if len(keys) > 1:
            raise SugarScriptLabelResolutionError(
                f"Cube alias '{alias}' node '{node_labels.node_key}' has duplicate "
                f"input label '{input_label}' for machine inputs: {', '.join(keys)}."
            )

    def _labels_for_global_input_key(self, input_key: str) -> set[str]:
        """Return visible labels observed for one machine input key."""

        labels: set[str] = set()
        for alias_labels in self._aliases.values():
            for node_labels in alias_labels.nodes_by_key.values():
                label = node_labels.input_labels_by_key.get(input_key)
                if label is not None:
                    labels.add(label)
        return labels

    def _public_endpoint_label(self, alias: str, endpoint_key: str) -> str:
        """Return a connect endpoint label while preserving endpoint prefixes."""

        _ = alias
        return endpoint_key


def resolve_parsed_script_labels(
    parsed_script: ParsedSugarScript,
    label_index: SugarScriptLabelIndex,
) -> ParsedSugarScript:
    """Return parsed SugarScript with label paths resolved to machine keys."""

    buffers: OrderedDict[str, JsonValue] = OrderedDict()
    for alias, buffer_data in parsed_script.buffers.items():
        resolved_buffer: OrderedDict[str, JsonValue] = OrderedDict()
        for key, value in buffer_data.items():
            if key == "nodes" and isinstance(value, Mapping):
                resolved_buffer[key] = _resolve_node_map(
                    alias=alias,
                    nodes=value,
                    label_index=label_index,
                )
            else:
                resolved_buffer[key] = value
        buffers[alias] = resolved_buffer
    return ParsedSugarScript(
        buffers=cast(Any, buffers),
        global_overrides=_resolve_global_override_keys(
            parsed_script.global_overrides,
            label_index,
        ),
        global_override_selections=_resolve_global_override_selection_keys(
            parsed_script.global_override_selections,
            label_index,
        ),
        field_control_states_by_alias=_resolve_field_control_state_keys(
            parsed_script.field_control_states_by_alias,
            label_index,
        ),
        override_control_states=_resolve_global_override_seed_control_keys(
            parsed_script.override_control_states,
            label_index,
        ),
        model_hashes_by_field=_resolve_model_hash_field_keys(
            parsed_script.model_hashes_by_field,
            label_index,
        ),
        prompt_lora_hashes_by_field=_resolve_prompt_lora_hash_field_keys(
            parsed_script.prompt_lora_hashes_by_field,
            label_index,
        ),
        project_name=parsed_script.project_name,
    )


def _resolve_field_control_state_keys(
    field_control_states_by_alias: Mapping[str, Mapping[str, Mapping[str, Any]]],
    label_index: SugarScriptLabelIndex,
) -> OrderedDict[str, OrderedDict[str, OrderedDict[str, Any]]]:
    """Resolve seed-control field labels to machine node and input keys."""

    resolved: OrderedDict[str, OrderedDict[str, OrderedDict[str, Any]]] = OrderedDict()
    for alias, node_states in field_control_states_by_alias.items():
        resolved_nodes: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
        for node_label, field_states in node_states.items():
            node_key = label_index.node_key_for_label(alias, str(node_label))
            resolved_fields: OrderedDict[str, Any] = OrderedDict()
            for input_label, state in field_states.items():
                input_key = label_index.input_key_for_label(
                    alias,
                    node_key,
                    str(input_label),
                )
                resolved_fields[input_key] = state
            resolved_nodes[node_key] = resolved_fields
        resolved[alias] = resolved_nodes
    return resolved


def _resolve_global_override_seed_control_keys(
    override_control_states: Mapping[str, Any],
    label_index: SugarScriptLabelIndex,
) -> OrderedDict[str, Any]:
    """Resolve global override seed-control labels to machine keys."""

    resolved: OrderedDict[str, Any] = OrderedDict()
    for key, state in override_control_states.items():
        resolved[label_index.global_input_key_for_label(str(key))] = state
    return resolved


def _resolve_model_hash_field_keys(
    model_hashes_by_field: Mapping[tuple[str, str, str], str],
    label_index: SugarScriptLabelIndex,
) -> OrderedDict[tuple[str, str, str], str]:
    """Return model hash metadata keyed by machine node and input keys."""

    resolved: OrderedDict[tuple[str, str, str], str] = OrderedDict()
    for (alias, node_label, input_label), sha256 in model_hashes_by_field.items():
        node_key = label_index.node_key_for_label(alias, node_label)
        input_key = label_index.input_key_for_label(alias, node_key, input_label)
        resolved[(alias, node_key, input_key)] = sha256
    return resolved


def _resolve_prompt_lora_hash_field_keys(
    prompt_lora_hashes_by_field: Mapping[tuple[str, str, str], Mapping[str, str]],
    label_index: SugarScriptLabelIndex,
) -> OrderedDict[tuple[str, str, str], OrderedDict[str, str]]:
    """Return inline LoRA hash metadata keyed by machine node and input keys."""

    resolved: OrderedDict[tuple[str, str, str], OrderedDict[str, str]] = OrderedDict()
    for (
        alias,
        node_label,
        input_label,
    ), prompt_hashes in prompt_lora_hashes_by_field.items():
        node_key = label_index.node_key_for_label(alias, node_label)
        input_key = label_index.input_key_for_label(alias, node_key, input_label)
        resolved[(alias, node_key, input_key)] = OrderedDict(prompt_hashes.items())
    return resolved


def _build_alias_labels(alias: str, graph: Mapping[str, Any]) -> _AliasLabels:
    """Build label mappings for one materialized cube graph."""

    runtime_graph = _runtime_graph_from_payload(graph)
    nodes = _mapping(runtime_graph.get("nodes"))
    layout_nodes = _mapping(_mapping(runtime_graph.get("layout")).get("nodes"))
    definitions = _mapping(runtime_graph.get("definitions"))
    surface_labels = _surface_control_labels(runtime_graph.get("surface"))
    subgraphs_by_id = _subgraphs_by_id(runtime_graph.get("subgraphs"))
    nodes_by_key: dict[str, _NodeLabels] = {}
    node_keys_by_label: defaultdict[str, list[str]] = defaultdict(list)
    for node_key, node_data in nodes.items():
        if not isinstance(node_data, Mapping):
            continue
        node_key_text = str(node_key)
        class_type = _text(node_data.get("class_type")) or ""
        node_label = _node_label(
            node_key=node_key_text,
            node_data=node_data,
            class_type=class_type,
            layout_node=layout_nodes.get(node_key_text),
            subgraph=subgraphs_by_id.get(class_type),
        )
        input_labels = _input_labels_for_node(
            node_key=node_key_text,
            node_data=node_data,
            class_type=class_type,
            definitions=definitions,
            surface_labels=surface_labels,
            subgraph=subgraphs_by_id.get(class_type),
            cube_alias=alias,
        )
        input_keys_by_label: defaultdict[str, list[str]] = defaultdict(list)
        for input_key, label in input_labels.items():
            input_keys_by_label[label].append(input_key)
        nodes_by_key[node_key_text] = _NodeLabels(
            node_key=node_key_text,
            label=node_label,
            input_labels_by_key=input_labels,
            input_keys_by_label={
                label: tuple(keys) for label, keys in input_keys_by_label.items()
            },
        )
        node_keys_by_label[node_label].append(node_key_text)
    return _AliasLabels(
        alias=alias,
        nodes_by_key=nodes_by_key,
        node_keys_by_label={
            label: tuple(keys) for label, keys in node_keys_by_label.items()
        },
    )


def _runtime_graph_from_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the runtime-shaped graph from runtime or canonical cube payloads."""

    implementation = payload.get("implementation")
    if not isinstance(implementation, Mapping):
        return payload
    runtime_graph = dict(implementation)
    for key in ("cube_id", "version", "surface", "flavors"):
        if key in payload:
            runtime_graph[key] = payload[key]
    return runtime_graph


def _node_label(
    *,
    node_key: str,
    node_data: Mapping[str, Any],
    class_type: str,
    layout_node: object,
    subgraph: Mapping[str, Any] | None,
) -> str:
    """Return the user-visible node label for one runtime node."""

    stored_label = _text(node_data.get("label"))
    if stored_label is not None:
        return stored_label
    if isinstance(layout_node, Mapping):
        layout_title = _text(layout_node.get("title"))
        if layout_title is not None:
            return layout_title
    meta = node_data.get("_meta")
    if isinstance(meta, Mapping):
        meta_title = _text(meta.get("title"))
        if meta_title is not None:
            return meta_title
    if is_subgraph_wrapper_class_type(class_type) and subgraph is not None:
        subgraph_name = _text(subgraph.get("name"))
        if subgraph_name is not None:
            return subgraph_name
    return node_key


def _input_labels_for_node(
    *,
    node_key: str,
    node_data: Mapping[str, Any],
    class_type: str,
    definitions: Mapping[str, Any],
    surface_labels: Mapping[tuple[str, str], str],
    subgraph: Mapping[str, Any] | None,
    cube_alias: str,
) -> dict[str, str]:
    """Return machine input keys mapped to script-visible labels."""

    inputs = _mapping(node_data.get("inputs"))
    labels: dict[str, str] = {}
    if is_subgraph_wrapper_class_type(class_type):
        if subgraph is None:
            raise SugarScriptLabelResolutionError(
                f"Cube alias '{cube_alias}' node '{node_key}' references missing "
                f"subgraph '{class_type}'."
            )
        labels.update(
            _subgraph_input_labels(
                subgraph=subgraph,
                cube_alias=cube_alias,
                node_key=node_key,
            )
        )
    definition = definitions.get(class_type)
    if isinstance(definition, Mapping):
        labels.update(_definition_input_labels(definition))
    for (symbol, input_name), surface_label in surface_labels.items():
        if symbol == node_key:
            labels[input_name] = surface_label
    for input_key in inputs:
        labels.setdefault(str(input_key), str(input_key))
    return labels


def _subgraph_input_labels(
    *,
    subgraph: Mapping[str, Any],
    cube_alias: str,
    node_key: str,
) -> dict[str, str]:
    """Return required public wrapper input labels from one subgraph."""

    entries = subgraph.get("inputs")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return {}
    labels: dict[str, str] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            continue
        input_name = _text(entry.get("name"))
        label = _text(entry.get("label"))
        if input_name is None:
            continue
        if label is None:
            raise SugarScriptLabelResolutionError(
                f"Cube alias '{cube_alias}' node '{node_key}' input '{input_name}' "
                "is missing required label."
            )
        labels[input_name] = label
        _ = index
    return labels


def _definition_input_labels(definition: Mapping[str, Any]) -> dict[str, str]:
    """Return visible input labels from a Comfy node definition."""

    input_section = _mapping(definition.get("input"))
    labels: dict[str, str] = {}
    for section_name in ("required", "optional"):
        section = _mapping(input_section.get(section_name))
        for input_key, raw_spec in section.items():
            label = _field_spec_label(raw_spec)
            labels[str(input_key)] = label or str(input_key)
    return labels


def _field_spec_label(raw_spec: object) -> str | None:
    """Return Comfy's visible label from one field definition."""

    if not isinstance(raw_spec, Sequence) or isinstance(raw_spec, (str, bytes)):
        return None
    values = list(raw_spec)
    if len(values) < 2 or not isinstance(values[1], Mapping):
        return None
    for key in ("label", "localized_name"):
        label = _text(values[1].get(key))
        if label is not None:
            return label
    return None


def _surface_control_labels(surface: object) -> dict[tuple[str, str], str]:
    """Return surface control labels keyed by node symbol and machine input."""

    if not isinstance(surface, Mapping):
        return {}
    controls = surface.get("controls")
    if not isinstance(controls, Sequence) or isinstance(controls, (str, bytes)):
        return {}
    labels: dict[tuple[str, str], str] = {}
    for control in controls:
        if not isinstance(control, Mapping):
            continue
        symbol = _text(control.get("symbol"))
        input_name = _text(control.get("input_name"))
        label = _text(control.get("label"))
        if symbol is None or input_name is None:
            continue
        if label is None:
            raise SugarScriptLabelResolutionError(
                f"Surface control '{symbol}.{input_name}' is missing required label."
            )
        labels[(symbol, input_name)] = label
    return labels


def _subgraphs_by_id(value: object) -> dict[str, Mapping[str, Any]]:
    """Return subgraph entries keyed by wrapper id."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return {}
    subgraphs: dict[str, Mapping[str, Any]] = {}
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        subgraph_id = _text(entry.get("id"))
        if subgraph_id is not None:
            subgraphs[subgraph_id] = entry
    return subgraphs


def _resolve_node_map(
    *,
    alias: str,
    nodes: Mapping[str, object],
    label_index: SugarScriptLabelIndex,
) -> OrderedDict[str, JsonValue]:
    """Resolve one parsed node map from labels to machine keys."""

    resolved_nodes: OrderedDict[str, JsonValue] = OrderedDict()
    for node_label, node_value in nodes.items():
        node_key = label_index.node_key_for_label(alias, str(node_label))
        node_payload = dict(node_value) if isinstance(node_value, Mapping) else {}
        resolved_node = _resolve_node_payload(
            alias=alias,
            node_key=node_key,
            node_payload=node_payload,
            label_index=label_index,
        )
        if node_key in resolved_nodes and isinstance(resolved_nodes[node_key], dict):
            _merge_node_payload(
                cast(dict[str, object], resolved_nodes[node_key]), resolved_node
            )
        else:
            resolved_nodes[node_key] = resolved_node
    return resolved_nodes


def _resolve_node_payload(
    *,
    alias: str,
    node_key: str,
    node_payload: dict[str, object],
    label_index: SugarScriptLabelIndex,
) -> JsonObject:
    """Resolve one parsed node payload from labels to machine keys."""

    resolved: JsonObject = {
        key: value for key, value in node_payload.items() if key != "inputs"
    }
    _resolve_link_metadata(resolved, label_index)
    raw_inputs = node_payload.get("inputs")
    if isinstance(raw_inputs, Mapping):
        resolved["inputs"] = _resolve_inputs(
            alias=alias,
            node_key=node_key,
            inputs=raw_inputs,
            node_payload=resolved,
            label_index=label_index,
        )
    return resolved


def _resolve_inputs(
    *,
    alias: str,
    node_key: str,
    inputs: Mapping[str, object],
    node_payload: JsonObject,
    label_index: SugarScriptLabelIndex,
) -> JsonObject:
    """Resolve parsed input labels and link references for one node."""

    resolved_inputs: JsonObject = {}
    for input_label, value in inputs.items():
        input_key = label_index.input_key_for_label(alias, node_key, str(input_label))
        resolved_value = _resolve_reference_value(value, label_index)
        if (
            input_key == "prompt_template"
            and isinstance(resolved_value, str)
            and _path_field_key(resolved_value) == "prompt_template"
        ):
            parts = _PATH_CODEC.split(resolved_value)
            node_payload["node_link"] = {
                "from_cube": parts[0],
                "from_node": parts[1],
            }
            resolved_inputs[input_key] = ""
            continue
        if input_key == "sampler_name" and isinstance(resolved_value, str):
            parts = _PATH_CODEC.split(resolved_value)
            if len(parts) == 3 and parts[2] == "sampler_name":
                node_payload["sampler_link"] = {
                    "from_cube": parts[0],
                    "from_node": parts[1],
                }
                continue
        if input_key == "scheduler" and isinstance(resolved_value, str):
            parts = _PATH_CODEC.split(resolved_value)
            if len(parts) == 3 and parts[2] == "scheduler":
                node_payload["scheduler_link"] = {
                    "from_cube": parts[0],
                    "from_node": parts[1],
                }
                continue
        resolved_inputs[input_key] = resolved_value
    return resolved_inputs


def _resolve_reference_value(
    value: object,
    label_index: SugarScriptLabelIndex,
) -> object:
    """Resolve a Sugar path value when it points at a labeled field."""

    if not isinstance(value, str):
        return value
    parts = _PATH_CODEC.split(value)
    if len(parts) != 3:
        return value
    alias, node_label, input_label = parts
    try:
        node_key = label_index.node_key_for_label(alias, node_label)
        input_key = label_index.input_key_for_label(alias, node_key, input_label)
    except SugarScriptLabelResolutionError:
        return value
    return f"{alias}.{node_key}.{input_key}"


def _resolve_link_metadata(
    node_payload: JsonObject,
    label_index: SugarScriptLabelIndex,
) -> None:
    """Resolve parsed node-link metadata that originated from label references."""

    for link_key in ("node_link", "sampler_link", "scheduler_link"):
        link_payload = node_payload.get(link_key)
        if not isinstance(link_payload, dict):
            continue
        from_cube = link_payload.get("from_cube")
        from_node = link_payload.get("from_node")
        if not isinstance(from_cube, str) or not isinstance(from_node, str):
            continue
        link_payload["from_node"] = label_index.node_key_for_label(
            from_cube,
            from_node,
        )


def _merge_node_payload(
    target: dict[str, object], source: Mapping[str, object]
) -> None:
    """Merge duplicate parsed node statements after label resolution."""

    for key, value in source.items():
        if key == "inputs" and isinstance(value, Mapping):
            target_inputs = target.setdefault("inputs", {})
            if isinstance(target_inputs, dict):
                target_inputs.update(value)
            continue
        target[key] = value


def _resolve_global_override_keys(
    overrides: GlobalOverrideMap,
    label_index: SugarScriptLabelIndex,
) -> GlobalOverrideMap:
    """Resolve global override labels back to machine keys."""

    resolved: GlobalOverrideMap = {}
    for key, value in overrides.items():
        resolved[label_index.global_input_key_for_label(str(key))] = value
    return resolved


def _resolve_global_override_selection_keys(
    selections: GlobalOverrideSelectionMap,
    label_index: SugarScriptLabelIndex,
) -> GlobalOverrideSelectionMap:
    """Resolve global override selection labels back to machine keys."""

    resolved: GlobalOverrideSelectionMap = {}
    for key, value in selections.items():
        resolved[label_index.global_input_key_for_label(str(key))] = value
    return resolved


def _path_field_key(value: str) -> str | None:
    """Return the field segment from a resolved three-part Sugar path."""

    parts = _PATH_CODEC.split(value)
    if len(parts) != 3:
        return None
    return parts[2]


def _mapping(value: object) -> Mapping[str, Any]:
    """Return a string-keyed mapping view for JSON objects."""

    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _text(value: object) -> str | None:
    """Return stripped non-empty text."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


__all__ = [
    "SugarScriptLabelIndex",
    "SugarScriptLabelResolutionError",
    "resolve_parsed_script_labels",
]
