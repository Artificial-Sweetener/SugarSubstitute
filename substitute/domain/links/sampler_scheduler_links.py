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

"""Provide sampler/scheduler link semantics independent of presentation widgets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

ChoiceItems = list[tuple[str, object]]


def _build_choice_items(
    link_items: object,
    literal_options: Sequence[str],
) -> ChoiceItems:
    """Build display labels and values for linked and literal choice options."""

    choice_items: ChoiceItems = []
    if isinstance(link_items, list):
        for link_info in link_items:
            if (
                isinstance(link_info, dict)
                and "from_cube" in link_info
                and "from_node" in link_info
            ):
                label = str(
                    link_info.get("label")
                    or f"-> {link_info['from_cube']} {link_info['from_node']}"
                )
                choice_items.append(
                    (
                        label,
                        {
                            "from_cube": link_info["from_cube"],
                            "from_node": link_info["from_node"],
                        },
                    )
                )
            elif isinstance(link_info, str):
                choice_items.append((link_info, link_info))

    for option in literal_options:
        choice_items.append((option, option))
    return choice_items


def build_sampler_choice_items(
    node_data: Mapping[str, Any],
    literal_options: Sequence[str],
) -> ChoiceItems:
    """Build display/value items for sampler combo boxes."""

    return _build_choice_items(node_data.get("sampler_links"), literal_options)


def build_scheduler_choice_items(
    node_data: Mapping[str, Any],
    literal_options: Sequence[str],
) -> ChoiceItems:
    """Build display/value items for scheduler combo boxes."""

    return _build_choice_items(node_data.get("scheduler_links"), literal_options)


def resolve_linked_choice_label(
    choice_items: Sequence[tuple[str, object]],
    link_value: object,
) -> str | None:
    """Resolve the display label for one linked choice value when present."""

    if not isinstance(link_value, Mapping):
        return None
    for label, value in choice_items:
        if not isinstance(value, Mapping):
            continue
        if value.get("from_cube") == link_value.get("from_cube") and value.get(
            "from_node"
        ) == link_value.get("from_node"):
            return label
    return None


def apply_choice_selection(
    node_data: dict[str, Any],
    *,
    literal_key: str,
    link_key: str,
    selected_value: object,
) -> None:
    """Apply one linked-or-literal combo box selection into node buffer data."""

    inputs = node_data.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
        node_data["inputs"] = inputs

    if selected_value is None:
        return

    if isinstance(selected_value, Mapping):
        node_data[link_key] = {
            "from_cube": selected_value.get("from_cube"),
            "from_node": selected_value.get("from_node"),
        }
        inputs.pop(literal_key, None)
        return

    inputs[literal_key] = selected_value
    node_data.pop(link_key, None)


def sanitize_sampler_link_selection(
    all_buffers: dict[str, dict[str, Any]],
    sampler_option_map: dict[tuple[str, str], list[str]],
) -> None:
    """Normalize invalid literal sampler values while preserving explicit links."""
    for cube_alias, cube in all_buffers.items():
        for node_name, node_data in cube.get("nodes", {}).items():
            inputs = node_data.get("inputs", {})
            if "sampler_name" not in inputs:
                continue
            options = sampler_option_map.get((cube_alias, node_name), [])
            current_value = inputs.get("sampler_name")
            sampler_link = node_data.get("sampler_link")
            if sampler_link is None and options and current_value not in options:
                inputs["sampler_name"] = options[0]


def sanitize_scheduler_link_selection(
    all_buffers: dict[str, dict[str, Any]],
    scheduler_option_map: dict[tuple[str, str], list[str]],
) -> None:
    """Normalize invalid literal scheduler values while preserving explicit links."""
    for cube_alias, cube in all_buffers.items():
        for node_name, node_data in cube.get("nodes", {}).items():
            inputs = node_data.get("inputs", {})
            if "scheduler" not in inputs:
                continue
            options = scheduler_option_map.get((cube_alias, node_name), [])
            current_value = inputs.get("scheduler")
            scheduler_link = node_data.get("scheduler_link")
            if scheduler_link is None and current_value not in options and options:
                inputs["scheduler"] = options[0]


def update_sampler_link_references_on_rename(
    all_buffers: dict[str, dict[str, Any]],
    old_alias: str,
    new_alias: str,
) -> None:
    """Rewrite sampler link references when a source cube alias is renamed."""
    for cube in all_buffers.values():
        for node in cube.get("nodes", {}).values():
            link = node.get("sampler_link", {})
            if isinstance(link, dict) and link.get("from_cube") == old_alias:
                link["from_cube"] = new_alias


def update_scheduler_link_references_on_rename(
    all_buffers: dict[str, dict[str, Any]],
    old_alias: str,
    new_alias: str,
) -> None:
    """Rewrite scheduler link references when a source cube alias is renamed."""
    for cube in all_buffers.values():
        for node in cube.get("nodes", {}).values():
            link = node.get("scheduler_link", {})
            if isinstance(link, dict) and link.get("from_cube") == old_alias:
                link["from_cube"] = new_alias


__all__ = [
    "apply_choice_selection",
    "build_sampler_choice_items",
    "build_scheduler_choice_items",
    "resolve_linked_choice_label",
    "sanitize_sampler_link_selection",
    "sanitize_scheduler_link_selection",
    "update_sampler_link_references_on_rename",
    "update_scheduler_link_references_on_rename",
]
