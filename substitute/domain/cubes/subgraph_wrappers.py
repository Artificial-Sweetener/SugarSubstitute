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

"""Build virtual node definitions for Comfy subgraph wrapper nodes."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Mapping, Pattern, Sequence

from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("domain.cubes.subgraph_wrappers")
DEFAULT_SOURCE_AUTHORED_PUBLIC_INTERFACE = "authored_public_interface"
DEFAULT_SOURCE_AUTHORED_BODY_WIDGET = "authored_body_widget"
DEFAULT_SOURCE_BODY_DEFINITION_FALLBACK = "body_definition_fallback"

UUID_CLASS_PATTERN: Pattern[str] = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def is_subgraph_wrapper_class_type(class_type: object) -> bool:
    """Return whether a class type is a Comfy subgraph wrapper UUID."""

    if not isinstance(class_type, str):
        return False
    normalized = class_type.strip()
    return bool(normalized and UUID_CLASS_PATTERN.match(normalized))


class SubgraphWrapperDefinitionIndex:
    """Resolve virtual node definitions for surface subgraph wrapper nodes."""

    def __init__(self, definitions: Mapping[str, Mapping[str, object]]) -> None:
        """Store virtual definitions keyed by subgraph wrapper class type."""

        self._definitions = {
            class_type: deepcopy(dict(definition))
            for class_type, definition in definitions.items()
        }

    @classmethod
    def from_runtime_graph(
        cls,
        graph: Mapping[str, object],
    ) -> SubgraphWrapperDefinitionIndex:
        """Build an index from a materialized cube runtime graph."""

        subgraphs = graph.get("subgraphs")
        if not isinstance(subgraphs, Sequence) or isinstance(subgraphs, (str, bytes)):
            return cls({})

        subgraph_entries = _subgraph_entries(subgraphs)
        node_definitions = _definition_map(graph.get("definitions"))
        definitions: dict[str, Mapping[str, object]] = {}
        for _ in range(max(1, len(subgraph_entries) + 1)):
            next_definitions: dict[str, Mapping[str, object]] = {}
            changed = False
            for subgraph_id, subgraph in subgraph_entries:
                available_definitions: dict[str, Mapping[str, object]] = {
                    **node_definitions,
                    **definitions,
                    **next_definitions,
                }
                definition = _virtual_definition_from_subgraph(
                    subgraph,
                    node_definitions=available_definitions,
                )
                if definition != definitions.get(subgraph_id):
                    changed = True
                next_definitions[subgraph_id] = definition
            definitions = next_definitions
            if not changed:
                break
        for subgraph_id, final_definition in definitions.items():
            _log_wrapper_definition_trace(
                subgraph_id=subgraph_id, definition=final_definition
            )
        return cls(definitions)

    def definition_for_class_type(
        self,
        class_type: str,
    ) -> Mapping[str, object] | None:
        """Return a virtual node definition for one wrapper class type."""

        if not is_subgraph_wrapper_class_type(class_type):
            return None
        definition = self._definitions.get(class_type)
        if definition is None:
            return None
        return deepcopy(dict(definition))

    def display_name_for_class_type(self, class_type: str) -> str | None:
        """Return the subgraph name for one wrapper class type."""

        if not is_subgraph_wrapper_class_type(class_type):
            return None
        definition = self._definitions.get(class_type)
        if definition is None:
            return None
        display_name = definition.get("display_name")
        if not isinstance(display_name, str):
            return None
        stripped = display_name.strip()
        return stripped or None

    def body_node_classes(self) -> tuple[str, ...]:
        """Return hidden body node classes referenced by wrapper public inputs."""

        body_classes: set[str] = set()
        for definition in self._definitions.values():
            body_classes.update(_body_node_classes_from_definition(definition))
        return tuple(sorted(body_classes))

    def body_node_classes_for_class_type(self, class_type: str) -> tuple[str, ...]:
        """Return hidden body node classes for one wrapper class type."""

        definition = self._definitions.get(class_type)
        if definition is None:
            return ()
        return tuple(sorted(_body_node_classes_from_definition(definition)))


@dataclass(frozen=True)
class _LinkedBodyInput:
    """Describe a hidden body input that backs one public wrapper input."""

    body_node_type: str
    body_input_name: str
    body_widget_value: object | None
    has_widget_value: bool


def _virtual_definition_from_subgraph(
    subgraph: Mapping[str, object],
    *,
    node_definitions: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Return a Comfy-like node definition for one subgraph wrapper."""

    subgraph_id = _normalized_text(subgraph.get("id")) or ""
    display_name = _normalized_text(subgraph.get("name")) or subgraph_id
    required_inputs: dict[str, object] = {}
    inputs = subgraph.get("inputs")
    if isinstance(inputs, Sequence) and not isinstance(inputs, (str, bytes)):
        for entry in inputs:
            if not isinstance(entry, Mapping):
                continue
            linked_body_input = _linked_body_input_for_interface_entry(
                subgraph=subgraph,
                interface_entry=entry,
            )
            body_type, body_metadata = _body_definition_metadata(
                linked_body_input=linked_body_input,
                node_definitions=node_definitions,
            )
            input_spec = _virtual_input_spec(
                entry,
                subgraph_id=subgraph_id,
                body_type=body_type,
                body_metadata=body_metadata,
                linked_body_input=linked_body_input,
            )
            if input_spec is None:
                continue
            field_name, field_spec = input_spec
            required_inputs[field_name] = field_spec

    output_types: list[str] = []
    output_names: list[str] = []
    outputs = subgraph.get("outputs")
    if isinstance(outputs, Sequence) and not isinstance(outputs, (str, bytes)):
        for entry in outputs:
            if not isinstance(entry, Mapping):
                continue
            output_name = _normalized_text(entry.get("name"))
            output_label = _required_public_interface_label(
                entry,
                subgraph_id=subgraph_id,
                field_name=output_name or "<unnamed>",
                direction="output",
            )
            output_type = _normalize_interface_type(entry.get("type"))
            output_types.append(output_type)
            output_names.append(output_label or output_type)

    return {
        "display_name": display_name,
        "description": "",
        "input": {
            "required": required_inputs,
            "optional": {},
            "hidden": {},
        },
        "output": output_types,
        "output_name": output_names,
        "name": subgraph_id,
        "subgraph_wrapper": True,
        "subgraph_id": subgraph_id,
    }


def _log_wrapper_definition_trace(
    *,
    subgraph_id: str,
    definition: Mapping[str, object],
) -> None:
    """Log wrapper-definition instrumentation for projection diagnostics."""

    input_section = definition.get("input")
    required = {}
    if isinstance(input_section, Mapping):
        required_raw = input_section.get("required")
        if isinstance(required_raw, Mapping):
            required = dict(required_raw)
    default_keys = []
    for field_key, field_spec in required.items():
        if (
            isinstance(field_key, str)
            and isinstance(field_spec, list)
            and len(field_spec) >= 2
            and isinstance(field_spec[1], Mapping)
            and "default" in field_spec[1]
        ):
            default_keys.append(field_key)
    outputs = definition.get("output")
    log_debug(
        _LOGGER,
        "Projected subgraph wrapper definition",
        subgraph_id=subgraph_id,
        display_name=definition.get("display_name"),
        input_keys=",".join(str(key) for key in required),
        default_keys=",".join(default_keys),
        output_count=len(outputs) if isinstance(outputs, list) else 0,
    )


def _virtual_input_spec(
    entry: Mapping[str, object],
    *,
    subgraph_id: str,
    body_type: object | None,
    body_metadata: Mapping[str, object],
    linked_body_input: _LinkedBodyInput | None,
) -> tuple[str, list[object]] | None:
    """Return one input field name and Comfy-like field spec."""

    field_name = _normalized_text(entry.get("name"))
    if field_name is None:
        return None
    _required_public_interface_label(
        entry,
        subgraph_id=subgraph_id,
        field_name=field_name,
        direction="input",
    )
    metadata = _public_interface_metadata(entry, subgraph_id=subgraph_id)
    if linked_body_input is not None:
        metadata["body_node_type"] = linked_body_input.body_node_type
        metadata["body_input_name"] = linked_body_input.body_input_name
    body_default = body_metadata.get("default")
    _merge_missing_metadata(metadata, body_metadata, include_default=False)
    if "default" in metadata:
        metadata["default_source"] = DEFAULT_SOURCE_AUTHORED_PUBLIC_INTERFACE
        metadata["has_authored_default"] = True
    elif linked_body_input is not None and linked_body_input.has_widget_value:
        metadata["default"] = deepcopy(linked_body_input.body_widget_value)
        metadata["default_source"] = DEFAULT_SOURCE_AUTHORED_BODY_WIDGET
        metadata["has_authored_default"] = True
    elif "default" in body_metadata:
        metadata["default"] = deepcopy(body_default)
        if body_metadata.get("has_authored_default") is True:
            metadata["default_source"] = body_metadata.get(
                "default_source",
                DEFAULT_SOURCE_AUTHORED_BODY_WIDGET,
            )
            metadata["has_authored_default"] = True
        else:
            metadata["default_source"] = DEFAULT_SOURCE_BODY_DEFINITION_FALLBACK
            metadata["has_authored_default"] = False
    _log_public_input_projection(
        subgraph_id=subgraph_id,
        public_input_name=field_name,
        linked_body_input=linked_body_input,
        body_metadata=body_metadata,
        merged_metadata=metadata,
    )
    return field_name, [
        _virtual_field_type(public_type=entry.get("type"), body_type=body_type),
        metadata,
    ]


def _public_interface_metadata(
    entry: Mapping[str, object],
    *,
    subgraph_id: str,
) -> dict[str, object]:
    """Return public interface metadata that is safe to expose on the wrapper."""

    metadata: dict[str, object] = {
        "subgraph_wrapper": True,
        "subgraph_id": subgraph_id,
    }
    label = _required_public_interface_label(
        entry,
        subgraph_id=subgraph_id,
        field_name=_normalized_text(entry.get("name")) or "<unnamed>",
        direction="input",
    )
    metadata["label"] = label
    localized_name = _normalized_text(entry.get("localized_name"))
    if localized_name is not None:
        metadata["localized_name"] = localized_name
    if "shape" in entry:
        metadata["shape"] = deepcopy(entry["shape"])
    if "id" in entry:
        metadata["interface_id"] = deepcopy(entry["id"])
    interface_type = _normalized_text(entry.get("type"))
    if interface_type is not None:
        metadata["interface_type"] = interface_type
    for key in (
        "default",
        "min",
        "max",
        "step",
        "tooltip",
        "options",
        "multiline",
        "dynamicPrompts",
        "placeholder",
    ):
        if key in entry:
            metadata[key] = deepcopy(entry[key])
    return metadata


def _merge_missing_metadata(
    metadata: dict[str, object],
    body_metadata: Mapping[str, object],
    *,
    include_default: bool,
) -> None:
    """Fill missing public metadata from the linked hidden body definition."""

    for key, value in body_metadata.items():
        if key == "default" and not include_default:
            continue
        if key not in metadata:
            metadata[key] = deepcopy(value)


def _virtual_field_type(
    *,
    public_type: object,
    body_type: object | None,
) -> object:
    """Return the wrapper field type while preserving the public interface shape."""

    normalized_public = _normalize_interface_type(public_type)
    if _should_use_concrete_body_type(normalized_public, body_type):
        return _concrete_body_type(body_type)
    if normalized_public != "ANY":
        return normalized_public
    concrete_body_type = _concrete_body_type(body_type)
    if concrete_body_type is not None:
        return concrete_body_type
    return normalized_public


def _should_use_concrete_body_type(
    public_type: str,
    body_type: object | None,
) -> bool:
    """Return whether a body widget type is more renderable than the public type."""

    return (public_type == "ANY" or "," in public_type) and _concrete_body_type(
        body_type
    ) is not None


def _concrete_body_type(body_type: object | None) -> object | None:
    """Return a concrete field type extracted from body metadata."""

    if isinstance(body_type, str):
        stripped = body_type.strip()
        if stripped:
            return stripped
    if isinstance(body_type, Sequence) and not isinstance(body_type, (str, bytes)):
        return "LIST"
    return None


def _log_public_input_projection(
    *,
    subgraph_id: str,
    public_input_name: str,
    linked_body_input: _LinkedBodyInput | None,
    body_metadata: Mapping[str, object],
    merged_metadata: Mapping[str, object],
) -> None:
    """Log public-input projection details for wrapper diagnostics."""

    constraint_keys = [key for key in ("min", "max", "step") if key in merged_metadata]
    log_debug(
        _LOGGER,
        "Projected subgraph wrapper input",
        subgraph_id=subgraph_id,
        public_input_name=public_input_name,
        body_metadata_found=bool(body_metadata),
        body_node_type=linked_body_input.body_node_type
        if linked_body_input is not None
        else "",
        body_input_name=linked_body_input.body_input_name
        if linked_body_input is not None
        else "",
        constraint_keys=",".join(constraint_keys),
        default_source=_default_source_for_projection(
            linked_body_input=linked_body_input,
            merged_metadata=merged_metadata,
            body_metadata=body_metadata,
        ),
    )


def _default_source_for_projection(
    *,
    linked_body_input: _LinkedBodyInput | None,
    merged_metadata: Mapping[str, object],
    body_metadata: Mapping[str, object],
) -> str:
    """Return a concise source label for temporary default instrumentation."""

    if "default" not in merged_metadata:
        return "none"
    if linked_body_input is not None and linked_body_input.has_widget_value:
        if merged_metadata.get("default") == linked_body_input.body_widget_value:
            return "body_widget"
    if "default" in body_metadata and merged_metadata.get(
        "default"
    ) == body_metadata.get("default"):
        return "body_definition"
    return "public_interface"


def _normalize_interface_type(value: object) -> str:
    """Return a stable Comfy type string for one subgraph interface entry."""

    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return "ANY"


def _required_public_interface_label(
    entry: Mapping[str, object],
    *,
    subgraph_id: str,
    field_name: str,
    direction: str,
) -> str:
    """Return the required current-format public interface label."""

    label = _normalized_text(entry.get("label"))
    if label is not None:
        return label
    raise ValueError(
        "Subgraph wrapper public "
        f"{direction} '{field_name}' in subgraph '{subgraph_id}' is missing "
        "required label."
    )


def _normalized_text(value: object) -> str | None:
    """Return stripped text for non-empty strings."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _definition_map(value: object) -> dict[str, Mapping[str, object]]:
    """Return node definitions keyed by class type from a cube-local payload."""

    definitions: dict[str, Mapping[str, object]] = {}
    if not isinstance(value, Mapping):
        return definitions
    for class_type, definition in value.items():
        if isinstance(class_type, str) and isinstance(definition, Mapping):
            definitions[class_type] = definition
    return definitions


def _subgraph_entries(
    subgraphs: Sequence[object],
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    """Return valid subgraph entries with normalized wrapper ids."""

    entries: list[tuple[str, Mapping[str, object]]] = []
    for subgraph in subgraphs:
        if not isinstance(subgraph, Mapping):
            continue
        subgraph_id = _normalized_text(subgraph.get("id"))
        if subgraph_id is not None:
            entries.append((subgraph_id, subgraph))
    return tuple(entries)


def _linked_body_input_for_interface_entry(
    *,
    subgraph: Mapping[str, object],
    interface_entry: Mapping[str, object],
) -> _LinkedBodyInput | None:
    """Resolve one public subgraph input to its hidden linked body widget input."""

    public_input_name = _normalized_text(interface_entry.get("name")) or ""
    links = _links_by_id(subgraph.get("links"))
    nodes = _nodes_by_id(subgraph.get("nodes"))
    input_node_ids = _interface_node_ids(subgraph.get("inputNode"), default="-10")
    for raw_link_id in _sequence_values(interface_entry.get("linkIds")):
        link_id = _normalized_node_id(raw_link_id)
        if link_id is None:
            continue
        link = links.get(link_id)
        if link is None:
            _log_body_input_resolution_failure(
                subgraph=subgraph,
                public_input_name=public_input_name,
                link_id=link_id,
                reason="missing_link",
            )
            continue
        if link.get("origin_id") not in input_node_ids:
            _log_body_input_resolution_failure(
                subgraph=subgraph,
                public_input_name=public_input_name,
                link_id=link_id,
                reason="link_not_from_input_node",
            )
            continue
        target_id = link.get("target_id")
        if not isinstance(target_id, str):
            continue
        target_node = nodes.get(target_id)
        body_input = _body_input_for_link(
            target_node=target_node,
            target_slot=link.get("target_slot"),
            link_id=link_id,
        )
        if body_input is None:
            _log_body_input_resolution_failure(
                subgraph=subgraph,
                public_input_name=public_input_name,
                link_id=link_id,
                reason="missing_widget_body_input",
            )
            continue
        body_node_type = _body_node_type(target_node)
        body_input_name = _body_input_name(body_input.entry)
        if body_node_type is None or body_input_name is None:
            _log_body_input_resolution_failure(
                subgraph=subgraph,
                public_input_name=public_input_name,
                link_id=link_id,
                reason="missing_body_type_or_input_name",
            )
            continue
        widget_value = _default_for_widget_input_index(
            target_node=target_node,
            target_index=body_input.index,
        )
        return _LinkedBodyInput(
            body_node_type=body_node_type,
            body_input_name=body_input_name,
            body_widget_value=widget_value,
            has_widget_value=widget_value is not None,
        )
    return None


@dataclass(frozen=True)
class _BodyInputEntry:
    """Describe a body input entry and its index in the serialized node inputs."""

    index: int
    entry: Mapping[str, object]


def _body_input_for_link(
    *,
    target_node: object,
    target_slot: object,
    link_id: str,
) -> _BodyInputEntry | None:
    """Return the widget-backed body input entry for one interface link."""

    if not isinstance(target_node, Mapping):
        return None
    inputs = target_node.get("inputs")
    if not isinstance(inputs, Sequence) or isinstance(inputs, (str, bytes)):
        return None
    for index, input_entry in enumerate(inputs):
        if (
            isinstance(input_entry, Mapping)
            and _normalized_node_id(input_entry.get("link")) == link_id
            and _is_widget_input(input_entry)
        ):
            return _BodyInputEntry(index=index, entry=input_entry)
    if isinstance(target_slot, int) and 0 <= target_slot < len(inputs):
        input_entry = inputs[target_slot]
        if _is_widget_input(input_entry):
            return _BodyInputEntry(index=target_slot, entry=input_entry)
    return None


def _is_widget_input(input_entry: object) -> bool:
    """Return whether one serialized body input is backed by a Comfy widget."""

    return isinstance(input_entry, Mapping) and isinstance(
        input_entry.get("widget"), Mapping
    )


def _body_node_type(target_node: object) -> str | None:
    """Return the class type for one hidden body node."""

    if not isinstance(target_node, Mapping):
        return None
    return _normalized_text(target_node.get("type")) or _normalized_text(
        target_node.get("class_type")
    )


def _body_input_name(input_entry: Mapping[str, object]) -> str | None:
    """Return the logical input name for one hidden body widget input."""

    widget = input_entry.get("widget")
    if isinstance(widget, Mapping):
        widget_name = _normalized_text(widget.get("name"))
        if widget_name is not None:
            return widget_name
    return _normalized_text(input_entry.get("name"))


def _default_for_widget_input_index(
    *,
    target_node: object,
    target_index: int,
) -> object | None:
    """Return the serialized widget default for one body input index."""

    if not isinstance(target_node, Mapping):
        return None
    inputs = target_node.get("inputs")
    values = target_node.get("widgets_values")
    if (
        not isinstance(inputs, Sequence)
        or isinstance(inputs, (str, bytes))
        or not isinstance(values, Sequence)
        or isinstance(values, (str, bytes))
        or target_index < 0
        or target_index >= len(inputs)
    ):
        return None
    widget_values = tuple(values)
    value_index = 0
    for input_index, input_entry in enumerate(inputs):
        if not _is_widget_input(input_entry):
            continue
        if input_index == target_index:
            if value_index >= len(widget_values):
                return None
            default_value: object = widget_values[value_index]
            return deepcopy(default_value)
        value_index += 1
        if isinstance(input_entry, Mapping) and _input_has_seed_control_after_generate(
            input_entry, values, value_index
        ):
            value_index += 1
    return None


def _body_definition_metadata(
    *,
    linked_body_input: _LinkedBodyInput | None,
    node_definitions: Mapping[str, Mapping[str, object]],
) -> tuple[object | None, dict[str, object]]:
    """Return a body field type and metadata for one linked hidden body input."""

    if linked_body_input is None:
        return None, {}
    node_definition = node_definitions.get(linked_body_input.body_node_type)
    if node_definition is None:
        return None, {}
    raw_field = _definition_field(
        node_definition=node_definition,
        input_name=linked_body_input.body_input_name,
    )
    if raw_field is None:
        return None, {}
    return _field_type_and_metadata(raw_field)


def _body_node_class_from_field_spec(field_spec: object) -> str | None:
    """Return the hidden body node class recorded on one wrapper field spec."""

    if (
        not isinstance(field_spec, Sequence)
        or isinstance(field_spec, (str, bytes))
        or len(field_spec) < 2
        or not isinstance(field_spec[1], Mapping)
    ):
        return None
    body_node_type = field_spec[1].get("body_node_type")
    if not isinstance(body_node_type, str):
        return None
    stripped = body_node_type.strip()
    return stripped or None


def _body_node_classes_from_definition(
    definition: Mapping[str, object],
) -> set[str]:
    """Return hidden body node classes referenced by one wrapper definition."""

    body_classes: set[str] = set()
    input_section = definition.get("input")
    if not isinstance(input_section, Mapping):
        return body_classes
    for section_name in ("required", "optional"):
        section = input_section.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for field_spec in section.values():
            body_class = _body_node_class_from_field_spec(field_spec)
            if body_class is not None:
                body_classes.add(body_class)
    return body_classes


def _definition_field(
    *,
    node_definition: Mapping[str, object],
    input_name: str,
) -> object | None:
    """Return one field definition from required or optional definition sections."""

    input_section = node_definition.get("input")
    if not isinstance(input_section, Mapping):
        return None
    for section_name in ("required", "optional"):
        section = input_section.get(section_name)
        if isinstance(section, Mapping) and input_name in section:
            field_definition: object = section[input_name]
            return field_definition
    return None


def _field_type_and_metadata(
    raw_field: object,
) -> tuple[object | None, dict[str, object]]:
    """Extract type and metadata from a Comfy field definition."""

    if not isinstance(raw_field, Sequence) or isinstance(raw_field, (str, bytes)):
        return None, {}
    values = tuple(raw_field)
    if not values:
        return None, {}
    field_type: object | None = deepcopy(values[0])
    metadata: dict[str, object] = {}
    if len(values) >= 2 and isinstance(values[1], Mapping):
        metadata = dict(values[1])
    if isinstance(values[0], Sequence) and not isinstance(values[0], (str, bytes)):
        metadata.setdefault("options", deepcopy(tuple(values[0])))
    return field_type, metadata


def _log_body_input_resolution_failure(
    *,
    subgraph: Mapping[str, object],
    public_input_name: str,
    link_id: str,
    reason: str,
) -> None:
    """Log why one public subgraph input could not resolve body metadata."""

    log_debug(
        _LOGGER,
        "Subgraph wrapper input metadata link resolution skipped",
        subgraph_id=_normalized_text(subgraph.get("id")) or "",
        subgraph_name=_normalized_text(subgraph.get("name")) or "",
        public_input_name=public_input_name,
        link_id=link_id,
        reason=reason,
    )


def _input_has_seed_control_after_generate(
    input_entry: Mapping[str, object],
    values: Sequence[object],
    value_index: int,
) -> bool:
    """Return whether a Comfy seed widget has an extra after-generate value."""

    if value_index >= len(values):
        return False
    widget = input_entry.get("widget")
    widget_name = widget.get("name") if isinstance(widget, Mapping) else None
    if widget_name != "seed":
        return False
    return isinstance(values[value_index], str)


def _links_by_id(raw_links: object) -> dict[str, dict[str, object]]:
    """Return normalized subgraph links keyed by serialized link id."""

    links: dict[str, dict[str, object]] = {}
    for fallback_id, raw_link in _collection_items(raw_links):
        normalized = _normalized_link(raw_link, fallback_id=fallback_id)
        if normalized is not None:
            link_id = normalized["id"]
            if isinstance(link_id, str):
                links[link_id] = normalized
    return links


def _normalized_link(
    raw_link: object,
    *,
    fallback_id: object = None,
) -> dict[str, object] | None:
    """Return a normalized object-style link from supported serialized forms."""

    if isinstance(raw_link, Mapping):
        link_id = _normalized_node_id(raw_link.get("id")) or _normalized_node_id(
            fallback_id
        )
        origin_id = _normalized_node_id(
            raw_link.get("origin_id") or raw_link.get("originId")
        )
        target_id = _normalized_node_id(
            raw_link.get("target_id") or raw_link.get("targetId")
        )
        target_slot = _normalized_int(
            raw_link.get("target_slot")
            if raw_link.get("target_slot") is not None
            else raw_link.get("targetSlot")
        )
    elif isinstance(raw_link, Sequence) and not isinstance(raw_link, (str, bytes)):
        values = list(raw_link)
        if len(values) < 5:
            return None
        link_id = _normalized_node_id(values[0])
        origin_id = _normalized_node_id(values[1])
        target_id = _normalized_node_id(values[3])
        target_slot = _normalized_int(values[4])
    else:
        return None
    if link_id is None or origin_id is None or target_id is None or target_slot is None:
        return None
    return {
        "id": link_id,
        "origin_id": origin_id,
        "target_id": target_id,
        "target_slot": target_slot,
    }


def _nodes_by_id(raw_nodes: object) -> dict[str, Mapping[str, object]]:
    """Return subgraph body nodes keyed by serialized node id."""

    nodes: dict[str, Mapping[str, object]] = {}
    for fallback_id, node in _collection_items(raw_nodes):
        if not isinstance(node, Mapping):
            continue
        node_id = _normalized_node_id(node.get("id")) or _normalized_node_id(
            fallback_id
        )
        if node_id is not None:
            nodes[node_id] = node
    return nodes


def _interface_node_ids(value: object, *, default: str) -> set[str]:
    """Return declared interface node ids, or the standard Comfy fallback id."""

    node_id = None
    if isinstance(value, Mapping):
        node_id = _normalized_node_id(value.get("id"))
    return {node_id} if node_id is not None else {default}


def _sequence_values(value: object) -> tuple[object, ...]:
    """Return tuple values from non-string sequences."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(value)


def _collection_items(value: object) -> tuple[tuple[object | None, object], ...]:
    """Return stable `(fallback_key, item)` entries from mappings or sequences."""

    if isinstance(value, Mapping):
        return tuple((key, item) for key, item in value.items())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple((None, item) for item in value)
    return ()


def _normalized_node_id(value: object) -> str | None:
    """Return a stable serialized id for links and nodes."""

    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value))
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _normalized_int(value: object) -> int | None:
    """Return an integer from serialized slot values."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


__all__ = [
    "DEFAULT_SOURCE_AUTHORED_BODY_WIDGET",
    "DEFAULT_SOURCE_AUTHORED_PUBLIC_INTERFACE",
    "DEFAULT_SOURCE_BODY_DEFINITION_FALLBACK",
    "SubgraphWrapperDefinitionIndex",
    "UUID_CLASS_PATTERN",
    "is_subgraph_wrapper_class_type",
]
