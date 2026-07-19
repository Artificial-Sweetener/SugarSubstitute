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

"""Resolve effective values for live Comfy list inputs outside presentation code."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from substitute.application.ports import NodeDefinitionGateway

from .models import FieldValueSource


@dataclass(frozen=True)
class ListValueResolution:
    """Describe the effective literal selected for one live list field."""

    effective_value: str
    value_source: FieldValueSource
    should_canonicalize: bool
    canonical_value: str | None


@dataclass(frozen=True)
class PickerFallback:
    """Describe a picker value derived from live Comfy metadata."""

    value: object
    source: str


class ChoiceAvailability(StrEnum):
    """Describe whether Comfy supplied a finite choice collection."""

    UNAVAILABLE = "unavailable"
    EMPTY = "empty"
    POPULATED = "populated"


@dataclass(frozen=True, slots=True)
class ChoiceInventory:
    """Publish one authoritative interpretation of Comfy choice metadata."""

    availability: ChoiceAvailability
    options: tuple[object, ...] = ()

    @property
    def string_options(self) -> tuple[str, ...]:
        """Return string literals suitable for editor choice controls."""

        return tuple(option for option in self.options if isinstance(option, str))

    @property
    def authoritative(self) -> bool:
        """Return whether Comfy explicitly supplied the option collection."""

        return self.availability is not ChoiceAvailability.UNAVAILABLE


def is_choice_field_type(field_type: object) -> bool:
    """Return whether a resolved field type represents a finite choice input."""

    return isinstance(field_type, str) and field_type in {"LIST", "COMBO"}


def _extract_string_options(value: object) -> tuple[str, ...]:
    """Return string options from a non-string sequence payload."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(option for option in value if isinstance(option, str))


def choice_inventory(field_info: object) -> ChoiceInventory:
    """Interpret classic and typed Comfy finite-choice definitions once."""

    if (
        not isinstance(field_info, Sequence)
        or isinstance(field_info, (str, bytes))
        or not field_info
    ):
        return ChoiceInventory(ChoiceAvailability.UNAVAILABLE)
    first_item = field_info[0]
    if isinstance(first_item, str) and first_item.upper() in {"COMBO", "LIST"}:
        if len(field_info) < 2 or not isinstance(field_info[1], Mapping):
            return ChoiceInventory(ChoiceAvailability.UNAVAILABLE)
        options = field_info[1].get("options")
        if not isinstance(options, Sequence) or isinstance(options, (str, bytes)):
            return ChoiceInventory(ChoiceAvailability.UNAVAILABLE)
        option_tuple = tuple(options)
        return ChoiceInventory(
            ChoiceAvailability.POPULATED if option_tuple else ChoiceAvailability.EMPTY,
            option_tuple,
        )
    if isinstance(first_item, Sequence) and not isinstance(first_item, (str, bytes)):
        option_tuple = tuple(first_item)
        return ChoiceInventory(
            ChoiceAvailability.POPULATED if option_tuple else ChoiceAvailability.EMPTY,
            option_tuple,
        )
    return ChoiceInventory(ChoiceAvailability.UNAVAILABLE)


def resolve_choice_inventory_for_field(
    *,
    key: str,
    node_type: object,
    node_definition_gateway: object,
    field_info: object,
) -> ChoiceInventory:
    """Resolve one field from live object-info before its prepared fallback."""

    if isinstance(node_type, str) and isinstance(
        node_definition_gateway, NodeDefinitionGateway
    ):
        payload = node_definition_gateway.get_node_definition(node_type)
        node_definition = payload.get(node_type)
        if isinstance(node_definition, Mapping):
            input_section = node_definition.get("input")
            if isinstance(input_section, Mapping):
                live_info: object = None
                for section_name in ("required", "optional"):
                    section = input_section.get(section_name)
                    if isinstance(section, Mapping) and key in section:
                        live_info = section[key]
                        break
                live_inventory = choice_inventory(live_info)
                if live_inventory.authoritative:
                    return live_inventory
    return choice_inventory(field_info)


def extract_picker_options(field_info: object) -> tuple[object, ...]:
    """Return all literal picker options from authoritative Comfy metadata."""

    return choice_inventory(field_info).options


def has_authoritative_picker_options(field_info: object) -> bool:
    """Return whether Comfy explicitly supplied a picker option collection."""

    return choice_inventory(field_info).authoritative


def extract_live_list_options(field_info: object) -> tuple[str, ...]:
    """Extract the live literal options from one Comfy field-definition payload."""

    if (
        not isinstance(field_info, Sequence)
        or isinstance(field_info, (str, bytes))
        or not field_info
    ):
        return ()

    return choice_inventory(field_info).string_options


def extract_picker_default(field_info: object) -> object | None:
    """Return the live default literal when picker metadata exposes one."""

    if (
        not isinstance(field_info, Sequence)
        or isinstance(field_info, (str, bytes))
        or len(field_info) < 2
        or not isinstance(field_info[1], Mapping)
    ):
        return None
    return field_info[1].get("default")


def extract_live_list_default(field_info: object) -> str | None:
    """Extract the live default literal when the definition exposes one."""

    default_value = extract_picker_default(field_info)
    return default_value if isinstance(default_value, str) else None


def is_picker_field_spec(field_info: object) -> bool:
    """Return whether object-info metadata describes a finite picker field."""

    if (
        not isinstance(field_info, Sequence)
        or isinstance(field_info, (str, bytes))
        or not field_info
    ):
        return False
    first_item = field_info[0]
    if isinstance(first_item, Sequence) and not isinstance(first_item, (str, bytes)):
        return True
    return isinstance(first_item, str) and first_item.upper() in {"COMBO", "LIST"}


def is_blank_picker_value(value: object) -> bool:
    """Return whether a picker value represents an unset selection."""

    return value is None or (isinstance(value, str) and not value.strip())


def resolve_picker_fallback(
    field_info: object,
    *,
    allow_first_option: bool,
) -> PickerFallback | None:
    """Return Comfy's valid explicit default or optional first choice."""

    options = extract_picker_options(field_info)
    default_value = extract_picker_default(field_info)
    if default_value is not None and (not options or default_value in options):
        return PickerFallback(value=default_value, source="default")
    if allow_first_option and options:
        return PickerFallback(value=options[0], source="first_option")
    return None


def unresolved_choice_options_reason(field_info: object) -> str | None:
    """Return why a finite choice field lacks concrete live options."""

    inventory = choice_inventory(field_info)
    if inventory.availability is ChoiceAvailability.POPULATED:
        return None
    if inventory.availability is ChoiceAvailability.EMPTY:
        return "empty_choice_options"
    if (
        not isinstance(field_info, Sequence)
        or isinstance(field_info, (str, bytes))
        or not field_info
    ):
        return "missing_field_definition"

    first_item = field_info[0]
    if isinstance(first_item, str) and first_item.upper() == "COMBO":
        return "missing_combo_options"
    if isinstance(first_item, str) and first_item.upper() == "LIST":
        return "missing_list_options"
    return None


def resolve_live_list_value(
    *,
    raw_value: object,
    field_info: Sequence[object] | None,
    remembered_value: str | None,
    clear_when_options_empty: bool = False,
) -> ListValueResolution | None:
    """Resolve the effective literal for one live list field.

    The resolver keeps presentation passive: it chooses the effective render value and
    reports whether the underlying buffer should be canonicalized, but it does not
    mutate any workflow state itself.
    """

    inventory = choice_inventory(field_info)
    options = inventory.string_options
    if not options:
        if clear_when_options_empty and inventory.authoritative:
            return ListValueResolution(
                effective_value="",
                value_source=FieldValueSource.NO_OPTIONS,
                should_canonicalize=raw_value != "",
                canonical_value="",
            )
        return None

    if isinstance(raw_value, str) and raw_value in options:
        return ListValueResolution(
            effective_value=raw_value,
            value_source=FieldValueSource.EXPLICIT,
            should_canonicalize=False,
            canonical_value=raw_value,
        )

    if isinstance(remembered_value, str) and remembered_value in options:
        return ListValueResolution(
            effective_value=remembered_value,
            value_source=FieldValueSource.FUTURE_USER_DEFAULT,
            should_canonicalize=raw_value != remembered_value,
            canonical_value=remembered_value,
        )

    live_default = extract_live_list_default(field_info)
    if isinstance(live_default, str) and live_default in options:
        return ListValueResolution(
            effective_value=live_default,
            value_source=FieldValueSource.LIVE_DEFAULT,
            should_canonicalize=raw_value != live_default,
            canonical_value=live_default,
        )

    first_option = options[0]
    return ListValueResolution(
        effective_value=first_option,
        value_source=FieldValueSource.FIRST_OPTION,
        should_canonicalize=raw_value != first_option,
        canonical_value=first_option,
    )


__all__ = [
    "ChoiceAvailability",
    "ChoiceInventory",
    "choice_inventory",
    "ListValueResolution",
    "PickerFallback",
    "extract_picker_default",
    "extract_picker_options",
    "extract_live_list_default",
    "extract_live_list_options",
    "has_authoritative_picker_options",
    "is_blank_picker_value",
    "is_choice_field_type",
    "is_picker_field_spec",
    "resolve_picker_fallback",
    "resolve_choice_inventory_for_field",
    "resolve_live_list_value",
    "unresolved_choice_options_reason",
]
