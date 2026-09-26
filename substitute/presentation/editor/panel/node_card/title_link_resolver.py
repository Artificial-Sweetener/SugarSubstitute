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

"""Resolve the node-link endpoint represented by a node-card title."""

from __future__ import annotations

from typing import Any

from substitute.application.node_behavior import ResolvedNodeBehavior, TitleControl


def resolve_title_node_link_endpoint(
    *,
    endpoint_index: Any,
    cube_alias: str,
    node_name: str,
    resolved_behavior: ResolvedNodeBehavior,
) -> Any | None:
    """Return the node-link endpoint controlled by one title row."""

    if TitleControl.PROMPT_LINK_SELECTOR in resolved_behavior.card.title_controls:
        prompt_roles = [
            field_behavior.prompt.role
            for field_behavior in resolved_behavior.fields.values()
            if field_behavior.prompt is not None and field_behavior.prompt.linkable
        ]
        if len(prompt_roles) != 1:
            return None
        endpoint = endpoint_index.prompt_endpoint_for(cube_alias, prompt_roles[0])
        if endpoint is not None and endpoint.node_name == node_name:
            return endpoint
        return None
    for identity in endpoint_index.identities_for_cube(cube_alias):
        endpoint = endpoint_index.endpoint_for(cube_alias, identity)
        if endpoint is not None and endpoint.node_name == node_name:
            return endpoint
    return None


__all__ = ["resolve_title_node_link_endpoint"]
