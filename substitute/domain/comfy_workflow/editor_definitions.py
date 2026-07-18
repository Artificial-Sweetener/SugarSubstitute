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

"""Build workflow-local editor definitions from serialized Comfy widgets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy

from substitute.domain.common import JsonObject


def editor_definition_for_widget_inputs(
    inputs: object,
    values: Mapping[str, object],
) -> JsonObject:
    """Return a minimal Comfy definition for serialized widget-backed inputs."""

    required: dict[str, object] = {}
    for item in _mapping_records(inputs):
        widget = item.get("widget")
        if not isinstance(widget, Mapping):
            continue
        input_name = item.get("name")
        if not isinstance(input_name, str) or input_name not in values:
            continue
        field_type = _field_type(item.get("type"))
        metadata = _widget_metadata(widget)
        metadata["default"] = deepcopy(values[input_name])
        required[input_name] = [field_type, metadata]
    return {"input": {"required": required}}


def editor_definition_from_comfy_definition(
    definition: Mapping[str, object] | None,
    values: Mapping[str, object],
) -> JsonObject | None:
    """Return local widget fields copied from live metadata with authored values."""

    if not isinstance(definition, Mapping):
        return None
    input_section = definition.get("input")
    if not isinstance(input_section, Mapping):
        return None
    required: dict[str, object] = {}
    optional: dict[str, object] = {}
    for section_name, target in (("required", required), ("optional", optional)):
        section = input_section.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for field_name, field_definition in section.items():
            if not isinstance(field_name, str) or field_name not in values:
                continue
            copied = _field_definition_with_default(
                field_definition,
                values[field_name],
            )
            if copied is not None:
                target[field_name] = copied
    local_input: dict[str, object] = {"required": required}
    if optional:
        local_input["optional"] = optional
    return {"input": local_input}


def editor_definition_for_value_proxy(
    node: Mapping[str, object],
) -> tuple[str, object, JsonObject]:
    """Return the one field and local definition owned by a value-proxy node."""

    outputs = _mapping_records(node.get("outputs"))
    if len(outputs) != 1:
        raise ValueError("Comfy value proxies must expose exactly one output.")
    output = outputs[0]
    widget = output.get("widget")
    if not isinstance(widget, Mapping):
        raise ValueError("Comfy value proxy output does not identify a widget.")
    widget_name = widget.get("name")
    if not isinstance(widget_name, str) or not widget_name.strip():
        raise ValueError("Comfy value proxy widget has no field name.")
    values = node.get("widgets_values")
    if (
        not isinstance(values, Sequence)
        or isinstance(values, str | bytes)
        or not values
    ):
        raise ValueError("Comfy value proxy has no serialized widget value.")
    field_key = widget_name.strip()
    value = deepcopy(values[0])
    metadata = _widget_metadata(widget)
    metadata["default"] = deepcopy(value)
    definition: JsonObject = {
        "input": {
            "required": {
                field_key: [_field_type(output.get("type")), metadata],
            }
        }
    }
    return field_key, value, definition


def workflow_local_editor_definition(
    node: Mapping[str, object],
) -> Mapping[str, object] | None:
    """Return a node instance's serialized editor definition when available."""

    workflow_metadata = node.get("_workflow")
    if not isinstance(workflow_metadata, Mapping):
        return None
    definition = workflow_metadata.get("editor_definition")
    return definition if isinstance(definition, Mapping) else None


def workflow_node_execution_role(
    node: Mapping[str, object],
) -> str:
    """Return the serialized execution role with executable fallback."""

    workflow_metadata = node.get("_workflow")
    if isinstance(workflow_metadata, Mapping):
        role = workflow_metadata.get("execution_role")
        if isinstance(role, str) and role.strip():
            return role.strip()
    return "executable"


def _mapping_records(payload: object) -> tuple[Mapping[str, object], ...]:
    """Return mapping records from a serialized Comfy array."""

    if not isinstance(payload, Sequence) or isinstance(payload, str | bytes):
        return ()
    return tuple(item for item in payload if isinstance(item, Mapping))


def _field_type(value: object) -> str:
    """Return a normalized Comfy widget field type."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return "STRING"


def _widget_metadata(widget: Mapping[str, object]) -> dict[str, object]:
    """Return serialized widget metadata excluding its structural field name."""

    return {str(key): deepcopy(value) for key, value in widget.items() if key != "name"}


def _field_definition_with_default(
    field_definition: object,
    value: object,
) -> list[object] | None:
    """Return a detached Comfy field definition with the workflow value as default."""

    if not isinstance(field_definition, Sequence) or isinstance(
        field_definition,
        str | bytes,
    ):
        return None
    copied = deepcopy(list(field_definition))
    if not copied:
        return None
    if len(copied) < 2 or not isinstance(copied[1], Mapping):
        copied.insert(1, {})
    metadata = deepcopy(dict(copied[1]))
    metadata["default"] = deepcopy(value)
    copied[1] = metadata
    return copied


__all__ = [
    "editor_definition_for_value_proxy",
    "editor_definition_for_widget_inputs",
    "editor_definition_from_comfy_definition",
    "workflow_local_editor_definition",
    "workflow_node_execution_role",
]
