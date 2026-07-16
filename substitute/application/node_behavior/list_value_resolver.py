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


def is_choice_field_type(field_type: object) -> bool:
    """Return whether a resolved field type represents a finite choice input."""

    return isinstance(field_type, str) and field_type in {"LIST", "COMBO"}


def _extract_string_options(value: object) -> tuple[str, ...]:
    """Return string options from a non-string sequence payload."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(option for option in value if isinstance(option, str))


def extract_picker_options(field_info: object) -> tuple[object, ...]:
    """Return all literal picker options from classic or COMBO metadata."""

    if (
        not isinstance(field_info, Sequence)
        or isinstance(field_info, (str, bytes))
        or not field_info
    ):
        return ()
    first_item = field_info[0]
    if first_item == "COMBO":
        if len(field_info) < 2 or not isinstance(field_info[1], Mapping):
            return ()
        options = field_info[1].get("options")
        if not isinstance(options, Sequence) or isinstance(options, (str, bytes)):
            return ()
        return tuple(options)
    if isinstance(first_item, Sequence) and not isinstance(first_item, (str, bytes)):
        return tuple(first_item)
    return ()


def has_authoritative_picker_options(field_info: object) -> bool:
    """Return whether Comfy explicitly supplied a picker option collection."""

    if (
        not isinstance(field_info, Sequence)
        or isinstance(field_info, (str, bytes))
        or not field_info
    ):
        return False
    first_item = field_info[0]
    if isinstance(first_item, Sequence) and not isinstance(first_item, (str, bytes)):
        return True
    if (
        isinstance(first_item, str)
        and first_item.upper() in {"COMBO", "LIST"}
        and len(field_info) > 1
        and isinstance(field_info[1], Mapping)
    ):
        options = field_info[1].get("options")
        return isinstance(options, Sequence) and not isinstance(options, (str, bytes))
    return False


def extract_live_list_options(field_info: object) -> tuple[str, ...]:
    """Extract the live literal options from one Comfy field-definition payload."""

    if (
        not isinstance(field_info, Sequence)
        or isinstance(field_info, (str, bytes))
        or not field_info
    ):
        return ()

    return _extract_string_options(extract_picker_options(field_info))


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

    if extract_live_list_options(field_info):
        return None
    if (
        not isinstance(field_info, Sequence)
        or isinstance(field_info, (str, bytes))
        or not field_info
    ):
        return "missing_field_definition"

    first_item = field_info[0]
    if first_item == "COMBO":
        return "missing_combo_options"
    if first_item == "LIST":
        return "missing_list_options"
    if isinstance(first_item, Sequence) and not isinstance(first_item, (str, bytes)):
        return "empty_list_options"
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

    options = extract_live_list_options(field_info)
    if not options:
        if clear_when_options_empty and has_authoritative_picker_options(field_info):
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
    "resolve_live_list_value",
    "unresolved_choice_options_reason",
]
