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

"""Provide prompt-link semantics independent of presentation widgets."""

from __future__ import annotations

from typing import Any

from substitute.domain.links.prompt_endpoints import PromptEndpointIndex
from substitute.domain.node_behavior.models import PromptRole


def find_first_cube_with_prompt(
    endpoint_index: PromptEndpointIndex,
    role: PromptRole,
    stack_order: list[str] | None = None,
) -> str | None:
    """Return the first cube alias containing the prompt role in stack order."""

    aliases = (
        stack_order
        if stack_order is not None
        else [endpoint.cube_alias for endpoint in endpoint_index.endpoints]
    )
    for cube_alias in aliases:
        if endpoint_index.endpoint_for(cube_alias, role) is not None:
            return cube_alias
    return None


def valid_link_options(
    this_cube_name: str,
    endpoint_index: PromptEndpointIndex,
    role: PromptRole,
    stack_order: list[str] | None = None,
) -> list[str]:
    """Return prompt-link target aliases that appear before the current cube."""

    aliases = (
        stack_order
        if stack_order is not None
        else [endpoint.cube_alias for endpoint in endpoint_index.endpoints]
    )
    return [
        endpoint.cube_alias
        for endpoint in endpoint_index.valid_link_targets(
            aliases,
            this_cube_name,
            role,
        )
    ]


def update_prompt_link_references_on_rename(
    all_buffers: dict[str, dict[str, Any]],
    old_alias: str,
    new_alias: str,
) -> None:
    """Rewrite prompt compatibility and canonical node-link source aliases."""

    for cube in all_buffers.values():
        for node in cube.get("nodes", {}).values():
            node_link = node.get("node_link", {})
            if isinstance(node_link, dict) and node_link.get("from_cube") == old_alias:
                node_link["from_cube"] = new_alias
            link = node.get("prompt_link", {})
            if isinstance(link, dict) and link.get("from_cube") == old_alias:
                link["from_cube"] = new_alias


__all__ = [
    "find_first_cube_with_prompt",
    "update_prompt_link_references_on_rename",
    "valid_link_options",
]
