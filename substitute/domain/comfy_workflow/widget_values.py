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

"""Map serialized LiteGraph widget values back to Comfy input names."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

_NUMERIC_CONTROL_VALUES = frozenset(
    {"fixed", "increment", "decrement", "randomize", "random"}
)


def node_widget_values(
    node: Mapping[str, object],
    node_definition: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return input-name widget values while skipping frontend-only controls."""

    serialized = node.get("widgets_values", ())
    if isinstance(serialized, Mapping):
        return {str(key): value for key, value in serialized.items()}
    if not isinstance(serialized, Sequence) or isinstance(serialized, str | bytes):
        return {}
    widget_inputs = _definition_widget_inputs(node_definition)
    if not widget_inputs:
        widget_inputs = _workflow_widget_inputs(node.get("inputs"))
    values = list(serialized)
    resolved: dict[str, object] = {}
    value_index = 0
    for input_index, (input_name, field_definition) in enumerate(widget_inputs):
        if value_index >= len(values):
            break
        remaining_inputs = len(widget_inputs) - input_index
        remaining_values = len(values) - value_index
        value = values[value_index]
        if (
            remaining_values > remaining_inputs
            and not _compatible_widget_value(value, field_definition)
            and value_index + 1 < len(values)
            and _compatible_widget_value(
                values[value_index + 1],
                field_definition,
            )
        ):
            value_index += 1
            value = values[value_index]
        resolved[input_name] = value
        value_index += 1
        if (
            _is_numeric_field(field_definition)
            and value_index < len(values)
            and isinstance(values[value_index], str)
            and values[value_index].casefold() in _NUMERIC_CONTROL_VALUES
            and len(values) - value_index > len(widget_inputs) - input_index - 1
        ):
            value_index += 1
    return resolved


def proxy_widget_values(
    node: Mapping[str, object],
) -> tuple[dict[str, object], dict[tuple[str, str], object]]:
    """Return subgraph interface and internal proxy widget overrides."""

    properties = node.get("properties")
    if not isinstance(properties, Mapping):
        return {}, {}
    proxies = properties.get("proxyWidgets")
    values = node.get("widgets_values")
    if not isinstance(proxies, Sequence) or isinstance(proxies, str | bytes):
        return {}, {}
    if not isinstance(values, Sequence) or isinstance(values, str | bytes):
        return {}, {}
    interface: dict[str, object] = {}
    internal: dict[tuple[str, str], object] = {}
    for proxy, value in zip(proxies, values, strict=False):
        if value is None or not isinstance(proxy, Sequence) or len(proxy) < 2:
            continue
        node_id, field_name = str(proxy[0]), str(proxy[1])
        if node_id == "-1":
            interface[field_name] = value
        elif field_name != "control_after_generate":
            internal[(node_id, field_name)] = value
    return interface, internal


def _workflow_widget_inputs(payload: object) -> tuple[tuple[str, object], ...]:
    """Return serialized inputs backed by named frontend widgets."""

    if not isinstance(payload, Sequence) or isinstance(payload, str | bytes):
        return ()
    result: list[tuple[str, object]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        widget = item.get("widget")
        if not isinstance(widget, Mapping) or not isinstance(widget.get("name"), str):
            continue
        name = item.get("name")
        if isinstance(name, str):
            result.append((name, [str(item.get("type", "")), {}]))
    return tuple(result)


def _definition_widget_inputs(
    definition: Mapping[str, object] | None,
) -> tuple[tuple[str, object], ...]:
    """Return ordered scalar widget fields from one live Comfy definition."""

    if not isinstance(definition, Mapping):
        return ()
    input_section = definition.get("input")
    if not isinstance(input_section, Mapping):
        return ()
    result: list[tuple[str, object]] = []
    for section_name in ("required", "optional"):
        section = input_section.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for field_name, field_definition in section.items():
            if isinstance(field_name, str) and _is_widget_field(field_definition):
                result.append((field_name, field_definition))
    return tuple(result)


def _is_widget_field(field_definition: object) -> bool:
    """Return whether a Comfy input definition is represented by a widget."""

    field_type = _field_type(field_definition)
    if isinstance(field_type, Sequence) and not isinstance(field_type, str | bytes):
        return True
    return isinstance(field_type, str) and field_type.upper() in {
        "BOOLEAN",
        "BOOL",
        "COMBO",
        "FLOAT",
        "INT",
        "INTEGER",
        "NUMBER",
        "STRING",
    }


def _compatible_widget_value(value: object, field_definition: object) -> bool:
    """Return whether a positional value plausibly belongs to an input type."""

    field_type = _field_type(field_definition)
    if isinstance(field_type, Sequence) and not isinstance(field_type, str | bytes):
        return not isinstance(value, Mapping | list | tuple)
    normalized = field_type.upper() if isinstance(field_type, str) else ""
    if normalized in {"INT", "INTEGER"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if normalized in {"FLOAT", "NUMBER"}:
        return isinstance(value, int | float) and not isinstance(value, bool)
    if normalized in {"BOOLEAN", "BOOL"}:
        return isinstance(value, bool)
    if normalized == "STRING":
        return isinstance(value, str)
    return True


def _is_numeric_field(field_definition: object) -> bool:
    """Return whether one field can own Comfy's numeric companion control."""

    field_type = _field_type(field_definition)
    return isinstance(field_type, str) and field_type.upper() in {
        "FLOAT",
        "INT",
        "INTEGER",
        "NUMBER",
    }


def _field_type(field_definition: object) -> object:
    """Return the leading type descriptor from one Comfy field definition."""

    if isinstance(field_definition, Sequence) and not isinstance(
        field_definition,
        str | bytes,
    ):
        return field_definition[0] if field_definition else None
    return field_definition


__all__ = ["node_widget_values", "proxy_widget_values"]
