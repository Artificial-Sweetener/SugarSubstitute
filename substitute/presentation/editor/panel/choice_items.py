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

"""Prepare finite-choice labels and backend values for editor controls."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from substitute.application.overrides.link_policy import (
    build_sampler_choice_items,
    build_scheduler_choice_items,
    resolve_linked_choice_label,
)

_COMBO_ITEM_CACHE_MAX_SIZE = 256
_COMBO_ITEM_CACHE: dict[
    tuple[str, tuple[str, ...], tuple[tuple[str, str, str], ...]],
    tuple[tuple[str, object], ...],
] = {}


def prepare_choice_items(
    *,
    key: str,
    node_data: object,
    options: Sequence[str],
) -> tuple[tuple[str, object], ...]:
    """Return cached display labels and independent backend values."""

    option_tuple = tuple(options)
    cache_key = (key, option_tuple, _link_signature(key=key, node_data=node_data))
    prepared = _COMBO_ITEM_CACHE.get(cache_key)
    if prepared is None:
        if key == "sampler_name" and isinstance(node_data, dict):
            raw_items = build_sampler_choice_items(node_data, option_tuple)
        elif key == "scheduler" and isinstance(node_data, dict):
            raw_items = build_scheduler_choice_items(node_data, option_tuple)
        else:
            raw_items = [(option, option) for option in option_tuple]
        prepared = tuple(
            (label, _freeze_item_value(value)) for label, value in raw_items
        )
        if len(_COMBO_ITEM_CACHE) >= _COMBO_ITEM_CACHE_MAX_SIZE:
            _COMBO_ITEM_CACHE.clear()
        _COMBO_ITEM_CACHE[cache_key] = prepared
    return tuple((label, _thaw_item_value(value)) for label, value in prepared)


def selected_choice_label(
    *,
    key: str,
    node_data: object,
    items: Sequence[tuple[str, object]],
    value: object,
) -> str:
    """Resolve the selected display label from literal or linked state."""

    if key in {"sampler_name", "scheduler"} and isinstance(node_data, dict):
        link_key = "sampler_link" if key == "sampler_name" else "scheduler_link"
        link = node_data.get(link_key)
        if isinstance(link, dict) and link:
            linked_label = resolve_linked_choice_label(items, link)
            if linked_label:
                return linked_label
    for label, item_value in items:
        if item_value == value:
            return label
    return items[0][0] if items else ""


def clear_choice_item_cache_for_tests() -> None:
    """Clear prepared choice rows for deterministic focused tests."""

    _COMBO_ITEM_CACHE.clear()


def _link_signature(
    *,
    key: str,
    node_data: object,
) -> tuple[tuple[str, str, str], ...]:
    """Return immutable link-choice inputs for preparation cache keys."""

    if not isinstance(node_data, dict):
        return ()
    link_key = (
        "sampler_links"
        if key == "sampler_name"
        else "scheduler_links"
        if key == "scheduler"
        else ""
    )
    link_items = node_data.get(link_key) if link_key else None
    if not isinstance(link_items, list):
        return ()
    signature: list[tuple[str, str, str]] = []
    for item in link_items:
        if isinstance(item, str):
            signature.append(("literal", item, ""))
        elif isinstance(item, dict):
            signature.append(
                (
                    str(item.get("label", "")),
                    str(item.get("from_cube", "")),
                    str(item.get("from_node", "")),
                )
            )
    return tuple(signature)


def _freeze_item_value(value: object) -> object:
    """Return an immutable representation of one backend value."""

    if isinstance(value, Mapping):
        return (
            "__linked_choice__",
            str(value.get("from_cube", "")),
            str(value.get("from_node", "")),
        )
    return value


def _thaw_item_value(value: object) -> object:
    """Return an independent mutable backend value when needed."""

    if isinstance(value, tuple) and len(value) == 3 and value[0] == "__linked_choice__":
        return {"from_cube": value[1], "from_node": value[2]}
    return value


__all__ = [
    "clear_choice_item_cache_for_tests",
    "prepare_choice_items",
    "selected_choice_label",
]
