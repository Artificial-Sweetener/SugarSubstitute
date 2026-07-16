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

"""Hydrate compiled prompts with local picker defaults from live Comfy metadata."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from copy import deepcopy

from substitute.application.node_behavior.list_value_resolver import (
    PickerFallback,
    extract_picker_options,
    is_blank_picker_value,
    is_picker_field_spec,
    resolve_picker_fallback as resolve_shared_picker_fallback,
)
from substitute.application.ports import NodeDefinitionGateway
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.recipes.picker_defaults")
_RUNTIME_ASSET_PICKER_FIELDS = frozenset(
    {
        ("LoadImage", "image"),
        ("LoadImageMask", "image"),
    }
)


class PickerDefaultResolutionError(RuntimeError):
    """Raised when a required picker has no valid local value."""


def hydrate_prompt_picker_defaults(
    workflow_nodes: MutableMapping[str, object],
    *,
    node_definition_gateway: NodeDefinitionGateway,
) -> None:
    """Validate and fill picker inputs against this Comfy installation."""

    cube_ids_by_alias = _cube_ids_by_alias(workflow_nodes)
    for node_id, node_payload in workflow_nodes.items():
        if not isinstance(node_payload, MutableMapping):
            continue
        class_type = _non_empty_string(node_payload.get("class_type"))
        if class_type is None:
            continue
        definition_payload = node_definition_gateway.get_required_node_definition(
            class_type
        )
        definition = definition_payload.get(class_type)
        if not isinstance(definition, Mapping):
            continue
        inputs = _node_inputs(node_payload)
        for input_name, field_spec in _iter_required_input_fields(definition):
            if not is_picker_field_spec(field_spec):
                continue
            if _is_runtime_asset_picker_field(class_type, input_name):
                continue
            context = _node_context(
                node_id,
                node_payload,
                cube_ids_by_alias=cube_ids_by_alias,
                class_type=class_type,
                input_name=input_name,
            )
            authored_value = inputs.get(input_name)
            if input_name not in inputs or is_blank_picker_value(authored_value):
                fallback = resolve_picker_fallback(field_spec)
                if fallback is None:
                    raise PickerDefaultResolutionError(
                        _missing_fallback_message(context)
                    )
                inputs[input_name] = deepcopy(fallback.value)
                log_debug(
                    _LOGGER,
                    "Filled missing picker input from local Comfy default",
                    **context,
                    fallback_source=fallback.source,
                )
                continue
            if _is_prompt_link(authored_value):
                continue
            options = picker_options(field_spec)
            if options and authored_value not in options:
                fallback = resolve_picker_fallback(field_spec)
                if fallback is None:
                    raise PickerDefaultResolutionError(
                        _missing_fallback_message(context)
                    )
                inputs[input_name] = deepcopy(fallback.value)
                log_debug(
                    _LOGGER,
                    "Replaced unavailable authored picker value with local Comfy default",
                    **context,
                    authored_value=authored_value,
                    fallback_source=fallback.source,
                )


def picker_options(field_spec: object) -> list[object]:
    """Return picker options from classic list and new API combo specs."""

    return list(extract_picker_options(field_spec))


def resolve_picker_fallback(field_spec: object) -> PickerFallback | None:
    """Return a valid local default or first local option for a picker."""

    return resolve_shared_picker_fallback(field_spec, allow_first_option=True)


def resolve_stable_picker_default(field_spec: object) -> PickerFallback | None:
    """Return a valid live default without using first-option fallback."""

    return resolve_shared_picker_fallback(field_spec, allow_first_option=False)


def _iter_required_input_fields(
    definition: Mapping[object, object],
) -> Sequence[tuple[str, object]]:
    """Return required input fields from one live object-info definition."""

    input_payload = definition.get("input")
    if not isinstance(input_payload, Mapping):
        return ()
    required = input_payload.get("required")
    if not isinstance(required, Mapping):
        return ()
    return tuple(
        (str(input_name), field_spec)
        for input_name, field_spec in required.items()
        if isinstance(input_name, str) and input_name
    )


def _node_inputs(
    node_payload: MutableMapping[object, object],
) -> MutableMapping[object, object]:
    """Return a mutable inputs mapping, creating it when absent."""

    inputs = node_payload.get("inputs")
    if isinstance(inputs, MutableMapping):
        return inputs
    created: dict[object, object] = {}
    node_payload["inputs"] = created
    return created


def _is_prompt_link(value: object) -> bool:
    """Return whether a value is a Comfy prompt link rather than a literal."""

    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)
    )


def _is_runtime_asset_picker_field(class_type: str, input_name: str) -> bool:
    """Return whether a picker carries a runtime asset reference."""

    return (class_type, input_name) in _RUNTIME_ASSET_PICKER_FIELDS


def _cube_ids_by_alias(workflow_nodes: Mapping[str, object]) -> dict[str, str]:
    """Return cube ids advertised by generated SugarCubes output nodes."""

    cube_ids: dict[str, str] = {}
    for node_payload in workflow_nodes.values():
        if not isinstance(node_payload, Mapping):
            continue
        if node_payload.get("class_type") != "SugarCubes.CubeOutput":
            continue
        inputs = node_payload.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        alias = _non_empty_string(inputs.get("instance_alias"))
        cube_id = _non_empty_string(inputs.get("cube_id"))
        if alias is not None and cube_id is not None:
            cube_ids[alias] = cube_id
    return cube_ids


def _node_context(
    node_id: str,
    node_payload: Mapping[object, object],
    *,
    cube_ids_by_alias: Mapping[str, str],
    class_type: str,
    input_name: str,
) -> dict[str, object]:
    """Build structured diagnostic context for picker fallback decisions."""

    substitute = node_payload.get("_meta")
    cube_alias: str | None = None
    node_name: str | None = None
    if isinstance(substitute, Mapping):
        metadata = substitute.get("substitute")
        if isinstance(metadata, Mapping):
            cube_alias = _non_empty_string(metadata.get("cube_alias"))
            node_name = _non_empty_string(metadata.get("node_name"))
    context: dict[str, object] = {
        "node_id": node_id,
        "class_type": class_type,
        "input_name": input_name,
    }
    if cube_alias is not None:
        context["cube_alias"] = cube_alias
        cube_id = cube_ids_by_alias.get(cube_alias)
        if cube_id is not None:
            context["cube_id"] = cube_id
    if node_name is not None:
        context["node_name"] = node_name
    return context


def _missing_fallback_message(context: Mapping[str, object]) -> str:
    """Return an actionable error message for a required picker with no fallback."""

    parts = [
        "No local Comfy picker default is available",
        f"class_type={context.get('class_type')}",
        f"input={context.get('input_name')}",
        f"node_id={context.get('node_id')}",
    ]
    if "cube_id" in context:
        parts.append(f"cube_id={context['cube_id']}")
    if "cube_alias" in context:
        parts.append(f"cube_alias={context['cube_alias']}")
    if "node_name" in context:
        parts.append(f"node_name={context['node_name']}")
    return "; ".join(parts)


def _non_empty_string(value: object) -> str | None:
    """Return a stripped non-empty string when available."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


__all__ = [
    "PickerDefaultResolutionError",
    "hydrate_prompt_picker_defaults",
    "is_picker_field_spec",
    "picker_options",
    "resolve_picker_fallback",
    "resolve_stable_picker_default",
]
