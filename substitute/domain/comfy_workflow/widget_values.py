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

from .native_widget_schema import decode_native_widget_values


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
    widget_inputs = _workflow_widget_inputs(node.get("inputs"))
    effective_definition = node_definition or {
        "input": {"required": dict(widget_inputs)}
    }
    decoded = decode_native_widget_values(effective_definition, serialized)
    if decoded.values:
        return decoded.values
    return {
        input_name: serialized[index]
        for index, (input_name, _field_definition) in enumerate(widget_inputs)
        if index < len(serialized)
    }


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


__all__ = ["node_widget_values", "proxy_widget_values"]
