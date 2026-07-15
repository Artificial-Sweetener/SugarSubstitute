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

"""Preflight required live picker values before Sugar serialization."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from copy import deepcopy
from dataclasses import dataclass

from substitute.application.ports import NodeDefinitionGateway
from substitute.application.recipes.picker_defaults import (
    is_picker_field_spec,
    picker_options,
)
from substitute.domain.common import JsonObject
from substitute.domain.recipes.sugar_ast import SugarBufferMap
from substitute.shared.logging.logger import get_logger, log_debug, log_error

_LOGGER = get_logger("application.recipes.required_picker_preflight")


@dataclass(frozen=True, slots=True)
class RequiredPickerValueError(RuntimeError):
    """Report a required picker whose blank value cannot be safely serialized."""

    cube_alias: str
    node_name: str
    class_type: str
    field_key: str
    raw_value: object
    fallback_source: str | None
    fallback_value: object | None

    def __str__(self) -> str:
        """Return an actionable user-facing message."""

        return (
            f"Select a value for {self.cube_alias}.{self.node_name}.{self.field_key} "
            "before saving, exporting, or generating. The field is required and "
            "the current cube value is blank."
        )


def prepare_required_picker_buffers(
    *,
    stripped_buffers: SugarBufferMap,
    ordered_aliases: Sequence[str],
    node_definition_gateway: NodeDefinitionGateway | None,
    enabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None = None,
    disabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None = None,
    required_node_definitions_by_class: MutableMapping[str, JsonObject] | None = None,
) -> SugarBufferMap:
    """Return serialization buffers with safe required picker defaults applied.

    Blank required picker fields are allowed to serialize only when Comfy exposes
    a stable live default. A first live option is not accepted because it can turn
    an unset model field into an unintended local checkpoint or loader choice.
    When a request-scoped definition cache is supplied, each node class queries
    live object-info at most once during that serialization request.
    """

    if node_definition_gateway is None:
        return stripped_buffers

    prepared_buffers: SugarBufferMap = deepcopy(stripped_buffers)
    for cube_alias in ordered_aliases:
        buffer = prepared_buffers.get(cube_alias)
        if not isinstance(buffer, MutableMapping):
            continue
        nodes = buffer.get("nodes")
        if not isinstance(nodes, MutableMapping):
            continue
        enabled_node_names = _enabled_node_names_for_alias(
            alias=cube_alias,
            enabled_node_keys_by_alias=enabled_node_keys_by_alias,
        )
        disabled_node_names = _disabled_node_names_for_alias(
            alias=cube_alias,
            disabled_node_keys_by_alias=disabled_node_keys_by_alias,
        )
        activation_overrides_provided = (
            enabled_node_keys_by_alias is not None
            or disabled_node_keys_by_alias is not None
        )
        for node_name, node in nodes.items():
            if not isinstance(node_name, str) or not isinstance(node, MutableMapping):
                continue
            if not _node_enabled(
                node_name=node_name,
                node=node,
                enabled_node_names=enabled_node_names,
                disabled_node_names=disabled_node_names,
                activation_overrides_provided=activation_overrides_provided,
            ):
                continue
            _prepare_node_required_pickers(
                cube_alias=cube_alias,
                node_name=node_name,
                node=node,
                node_definition_gateway=node_definition_gateway,
                required_node_definitions_by_class=(required_node_definitions_by_class),
            )
    return prepared_buffers


def _prepare_node_required_pickers(
    *,
    cube_alias: str,
    node_name: str,
    node: MutableMapping[object, object],
    node_definition_gateway: NodeDefinitionGateway,
    required_node_definitions_by_class: MutableMapping[str, JsonObject] | None,
) -> None:
    """Validate and fill blank required pickers for one executable node."""

    class_type = node.get("class_type")
    if not isinstance(class_type, str) or not class_type:
        return
    definition_payload: JsonObject
    if required_node_definitions_by_class is None:
        definition_payload = node_definition_gateway.get_required_node_definition(
            class_type
        )
    else:
        cached_definition_payload = required_node_definitions_by_class.get(class_type)
        if cached_definition_payload is None:
            definition_payload = node_definition_gateway.get_required_node_definition(
                class_type
            )
            required_node_definitions_by_class[class_type] = definition_payload
        else:
            definition_payload = cached_definition_payload
    definition = definition_payload.get(class_type)
    if not isinstance(definition, Mapping):
        return
    inputs = _mutable_node_inputs(node)
    for field_key, field_spec in _required_picker_fields(definition):
        raw_value = inputs.get(field_key)
        if field_key in inputs and not _is_blank_picker_value(raw_value):
            continue
        default_value = _stable_default_value(field_spec)
        if default_value is not None:
            inputs[field_key] = deepcopy(default_value)
            log_debug(
                _LOGGER,
                "Filled blank required picker value from live default",
                cube_alias=cube_alias,
                node_name=node_name,
                class_type=class_type,
                field_key=field_key,
                raw_value=raw_value,
                value_source="live_default",
                resolved_value=default_value,
            )
            continue
        fallback_value = _first_option_value(field_spec)
        error = RequiredPickerValueError(
            cube_alias=cube_alias,
            node_name=node_name,
            class_type=class_type,
            field_key=field_key,
            raw_value=raw_value,
            fallback_source="first_option" if fallback_value is not None else None,
            fallback_value=fallback_value,
        )
        log_error(
            _LOGGER,
            "Blocked blank required picker value before serialization",
            cube_alias=cube_alias,
            node_name=node_name,
            class_type=class_type,
            field_key=field_key,
            raw_value=raw_value,
            value_source=error.fallback_source,
            resolved_value=error.fallback_value,
        )
        raise error


def _required_picker_fields(
    definition: Mapping[object, object],
) -> tuple[tuple[str, object], ...]:
    """Return required live picker fields from one node definition."""

    input_section = definition.get("input")
    if not isinstance(input_section, Mapping):
        return ()
    required = input_section.get("required")
    if not isinstance(required, Mapping):
        return ()
    return tuple(
        (field_key, field_spec)
        for field_key, field_spec in required.items()
        if isinstance(field_key, str) and is_picker_field_spec(field_spec)
    )


def _mutable_node_inputs(
    node: MutableMapping[object, object],
) -> MutableMapping[object, object]:
    """Return a mutable node input map, creating it when absent."""

    inputs = node.get("inputs")
    if isinstance(inputs, MutableMapping):
        return inputs
    created: dict[object, object] = {}
    node["inputs"] = created
    return created


def _is_blank_picker_value(value: object) -> bool:
    """Return whether a picker value is absent or blank text."""

    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def _stable_default_value(field_spec: object) -> object | None:
    """Return a live default value when it is valid for the picker."""

    metadata = _field_metadata(field_spec)
    if metadata is None or "default" not in metadata:
        return None
    default_value = metadata["default"]
    options = picker_options(field_spec)
    if options and default_value not in options:
        return None
    return default_value


def _first_option_value(field_spec: object) -> object | None:
    """Return the first available option for diagnostics only."""

    options = picker_options(field_spec)
    return options[0] if options else None


def _field_metadata(field_spec: object) -> Mapping[object, object] | None:
    """Return field metadata from a live Comfy field spec."""

    if (
        isinstance(field_spec, Sequence)
        and not isinstance(field_spec, (str, bytes))
        and len(field_spec) > 1
        and isinstance(field_spec[1], Mapping)
    ):
        return field_spec[1]
    return None


def _disabled_node_names_for_alias(
    *,
    alias: str,
    disabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None,
) -> frozenset[str]:
    """Return policy-disabled node names for one alias."""

    if disabled_node_keys_by_alias is None:
        return frozenset()
    return frozenset(
        str(node_name) for node_name in disabled_node_keys_by_alias.get(alias, ())
    )


def _enabled_node_names_for_alias(
    *,
    alias: str,
    enabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None,
) -> frozenset[str]:
    """Return policy-enabled node names for one alias."""

    if enabled_node_keys_by_alias is None:
        return frozenset()
    return frozenset(
        str(node_name) for node_name in enabled_node_keys_by_alias.get(alias, ())
    )


def _node_enabled(
    *,
    node_name: str,
    node: Mapping[object, object],
    enabled_node_names: frozenset[str],
    disabled_node_names: frozenset[str],
    activation_overrides_provided: bool,
) -> bool:
    """Return whether one node participates in serialization."""

    if activation_overrides_provided:
        if node_name in enabled_node_names:
            return True
        if node_name in disabled_node_names:
            return False
        return not _is_authored_bypass_node(node)
    explicit_enabled = node.get("enabled")
    if isinstance(explicit_enabled, bool):
        return explicit_enabled
    return not _is_authored_bypass_node(node)


def _is_authored_bypass_node(node: Mapping[object, object]) -> bool:
    """Return whether a node payload carries authored LiteGraph bypass mode."""

    mode = node.get("mode")
    return isinstance(mode, int) and not isinstance(mode, bool) and mode == 4


__all__ = [
    "RequiredPickerValueError",
    "prepare_required_picker_buffers",
]
