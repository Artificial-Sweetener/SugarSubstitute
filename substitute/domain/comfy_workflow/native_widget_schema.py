#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Interpret native Comfy widget schemas without presentation dependencies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass

_DYNAMIC_COMBO_TYPE = "COMFY_DYNAMICCOMBO_V3"
_AUTOGROW_TYPE = "COMFY_AUTOGROW_V3"
_SCALAR_WIDGET_TYPES = frozenset(
    {
        "AUDIO_RECORD",
        "BOOLEAN",
        "BOOL",
        "BOUNDING_BOX",
        "COLOR",
        "COMBO",
        "CURVE",
        "FLOAT",
        "INT",
        "INTEGER",
        "NUMBER",
        "STRING",
    }
)
_NUMERIC_WIDGET_TYPES = frozenset({"FLOAT", "INT", "INTEGER", "NUMBER"})
_NUMERIC_CONTROL_VALUES = frozenset(
    {"fixed", "increment", "decrement", "randomize", "random"}
)
_CUSTOM_WIDGET_SERIALIZED_ARITY = {"LOAD_3D": 1}


@dataclass(frozen=True, slots=True)
class NativeWidgetDecoding:
    """Contain decoded values and the active normalized editor definition."""

    values: dict[str, object]
    definition: dict[str, object]


class _WidgetValueCursor:
    """Consume one serialized LiteGraph widget stream in schema order."""

    def __init__(self, values: Sequence[object]) -> None:
        """Copy serialized values so traversal cannot mutate workflow data."""

        self._values = tuple(values)
        self._index = 0

    def take(self, field_definition: object) -> object | None:
        """Return the next compatible value and advance past numeric companions."""

        if self._index >= len(self._values):
            return None
        value = self._values[self._index]
        if (
            not _compatible_widget_value(value, field_definition)
            and self._index + 1 < len(self._values)
            and _compatible_widget_value(
                self._values[self._index + 1],
                field_definition,
            )
        ):
            self._index += 1
            value = self._values[self._index]
        self._index += 1
        if _is_numeric_field(field_definition) and self._is_numeric_companion_next():
            self._index += 1
        return deepcopy(value)

    def discard(self, count: int) -> None:
        """Advance past serialized frontend-only widget values."""

        self._index = min(len(self._values), self._index + max(0, count))

    def _is_numeric_companion_next(self) -> bool:
        """Return whether the next serialized value is Comfy's numeric mode control."""

        if self._index >= len(self._values):
            return False
        value = self._values[self._index]
        return isinstance(value, str) and value.casefold() in _NUMERIC_CONTROL_VALUES


def decode_native_widget_values(
    definition: Mapping[str, object] | None,
    serialized: Sequence[object],
) -> NativeWidgetDecoding:
    """Decode serialized widget values and publish the selected native schema."""

    cursor = _WidgetValueCursor(serialized)
    values: dict[str, object] = {}
    normalized = _walk_definition(
        definition,
        selected_values=values,
        cursor=cursor,
        prefix="",
    )
    return NativeWidgetDecoding(values=values, definition=normalized)


def normalize_native_widget_definition(
    definition: Mapping[str, object] | None,
    selected_values: Mapping[str, object],
) -> dict[str, object]:
    """Expand active dynamic inputs and normalize their selector definitions."""

    return _walk_definition(
        definition,
        selected_values=dict(selected_values),
        cursor=None,
        prefix="",
    )


def _walk_definition(
    definition: Mapping[str, object] | None,
    *,
    selected_values: dict[str, object],
    cursor: _WidgetValueCursor | None,
    prefix: str,
) -> dict[str, object]:
    """Return one definition with active dynamic descendants flattened by path."""

    if not isinstance(definition, Mapping):
        return {}
    normalized = deepcopy(dict(definition))
    input_section = definition.get("input")
    if not isinstance(input_section, Mapping):
        return normalized
    normalized_input: dict[str, object] = {}
    for section_name in ("required", "optional"):
        section = input_section.get(section_name)
        if not isinstance(section, Mapping):
            continue
        normalized_section: dict[str, object] = {}
        _walk_section(
            section,
            target=normalized_section,
            selected_values=selected_values,
            cursor=cursor,
            prefix=prefix,
        )
        if normalized_section or section_name == "required":
            normalized_input[section_name] = normalized_section
    for key, value in input_section.items():
        if key not in {"required", "optional"}:
            normalized_input[str(key)] = deepcopy(value)
    normalized["input"] = normalized_input
    return normalized


def _walk_section(
    section: Mapping[str, object],
    *,
    target: dict[str, object],
    selected_values: dict[str, object],
    cursor: _WidgetValueCursor | None,
    prefix: str,
) -> None:
    """Append one required/optional section and its active dynamic descendants."""

    for raw_name, field_definition in section.items():
        if not isinstance(raw_name, str):
            continue
        field_name = f"{prefix}{raw_name}"
        field_type = _normalized_field_type(field_definition)
        if field_type == _DYNAMIC_COMBO_TYPE:
            selector = selected_values.get(field_name)
            if cursor is not None:
                selector = cursor.take(field_definition)
                if selector is not None:
                    selected_values[field_name] = selector
            target[field_name] = _normalized_dynamic_selector(field_definition)
            option_inputs = _selected_dynamic_inputs(field_definition, selector)
            if option_inputs is not None:
                nested = _walk_definition(
                    {"input": option_inputs},
                    selected_values=selected_values,
                    cursor=cursor,
                    prefix=f"{field_name}.",
                )
                _merge_nested_sections(target, nested)
            continue
        normalized_field_definition = _normalized_widget_type_definition(
            field_definition
        )
        target[field_name] = normalized_field_definition
        if field_type == _AUTOGROW_TYPE:
            continue
        if cursor is not None and field_type in _CUSTOM_WIDGET_SERIALIZED_ARITY:
            cursor.discard(
                _custom_widget_serialized_arity(
                    field_type,
                    section=section,
                )
            )
            continue
        if not _is_widget_field(normalized_field_definition):
            continue
        if cursor is not None:
            value = cursor.take(normalized_field_definition)
            if value is not None:
                selected_values[field_name] = value


def _merge_nested_sections(
    target: dict[str, object],
    nested_definition: Mapping[str, object],
) -> None:
    """Merge flattened active descendants into their parent's editor section."""

    nested_input = nested_definition.get("input")
    if not isinstance(nested_input, Mapping):
        return
    for section_name in ("required", "optional"):
        section = nested_input.get(section_name)
        if isinstance(section, Mapping):
            target.update(deepcopy(dict(section)))


def _normalized_dynamic_selector(field_definition: object) -> list[object]:
    """Return a standard COMBO definition for one native dynamic selector."""

    metadata = _field_metadata(field_definition)
    options = metadata.get("options")
    option_keys = (
        [
            option.get("key")
            for option in options
            if isinstance(option, Mapping) and isinstance(option.get("key"), str)
        ]
        if isinstance(options, Sequence) and not isinstance(options, str | bytes)
        else []
    )
    normalized_metadata = deepcopy(metadata)
    normalized_metadata["options"] = option_keys
    normalized_metadata["native_widget_type"] = _DYNAMIC_COMBO_TYPE
    return ["COMBO", normalized_metadata]


def _normalized_widget_type_definition(field_definition: object) -> object:
    """Apply Comfy's explicit editor widget override to a socket definition."""

    if (
        not isinstance(field_definition, Sequence)
        or isinstance(field_definition, str | bytes)
        or not field_definition
    ):
        return deepcopy(field_definition)
    metadata = _field_metadata(field_definition)
    widget_type = metadata.get("widgetType")
    if not isinstance(widget_type, str):
        return deepcopy(field_definition)
    normalized_widget_type = widget_type.upper()
    if normalized_widget_type not in _SCALAR_WIDGET_TYPES:
        return deepcopy(field_definition)
    native_socket_type = field_definition[0]
    metadata["native_socket_type"] = deepcopy(native_socket_type)
    return [
        normalized_widget_type,
        metadata,
        *deepcopy(list(field_definition[2:])),
    ]


def _custom_widget_serialized_arity(
    field_type: str,
    *,
    section: Mapping[str, object],
) -> int:
    """Return native frontend values owned by one custom widget surface."""

    base_arity = _CUSTOM_WIDGET_SERIALIZED_ARITY[field_type]
    if field_type == "LOAD_3D" and "model_file" in section:
        return base_arity + 3
    return base_arity


def _selected_dynamic_inputs(
    field_definition: object,
    selector: object,
) -> Mapping[str, object] | None:
    """Return the input definition owned by the selected dynamic option."""

    options = _field_metadata(field_definition).get("options")
    if not isinstance(options, Sequence) or isinstance(options, str | bytes):
        return None
    for option in options:
        if not isinstance(option, Mapping) or option.get("key") != selector:
            continue
        inputs = option.get("inputs")
        return inputs if isinstance(inputs, Mapping) else None
    return None


def _is_widget_field(field_definition: object) -> bool:
    """Return whether a native definition consumes a serialized widget value."""

    field_type = _field_type(field_definition)
    if isinstance(field_type, Sequence) and not isinstance(field_type, str | bytes):
        return True
    return isinstance(field_type, str) and field_type.upper() in _SCALAR_WIDGET_TYPES


def _compatible_widget_value(value: object, field_definition: object) -> bool:
    """Return whether a serialized value plausibly belongs to one widget type."""

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
    if normalized == "COLOR":
        return isinstance(value, str)
    if normalized in {"BOUNDING_BOX", "CURVE"}:
        return isinstance(value, Mapping)
    if normalized == "AUDIO_RECORD":
        return value is None or isinstance(value, str)
    return True


def _is_numeric_field(field_definition: object) -> bool:
    """Return whether a definition owns Comfy's numeric companion control."""

    return _normalized_field_type(field_definition) in _NUMERIC_WIDGET_TYPES


def _normalized_field_type(field_definition: object) -> str:
    """Return an uppercase scalar type name or an empty string."""

    field_type = _field_type(field_definition)
    return field_type.upper() if isinstance(field_type, str) else ""


def _field_type(field_definition: object) -> object:
    """Return the leading type descriptor from one Comfy field definition."""

    if isinstance(field_definition, Sequence) and not isinstance(
        field_definition,
        str | bytes,
    ):
        return field_definition[0] if field_definition else None
    return field_definition


def _field_metadata(field_definition: object) -> dict[str, object]:
    """Return detached metadata from one Comfy field definition."""

    if (
        not isinstance(field_definition, Sequence)
        or isinstance(field_definition, str | bytes)
        or len(field_definition) < 2
        or not isinstance(field_definition[1], Mapping)
    ):
        return {}
    return deepcopy(dict(field_definition[1]))


__all__ = [
    "NativeWidgetDecoding",
    "decode_native_widget_values",
    "normalize_native_widget_definition",
]
