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

"""Expose domain link-semantics helpers for prompt/sampler/scheduler behavior."""

from __future__ import annotations

from .node_links import (
    NodeLinkEndpoint,
    NodeLinkEndpointIndex,
    NodeLinkIdentity,
    NodeLinkReference,
    update_node_link_references_on_rename,
)
from .prompt_links import (
    find_first_cube_with_prompt,
    update_prompt_link_references_on_rename,
    valid_link_options,
)
from .prompt_endpoints import PromptEndpoint, PromptEndpointIndex
from .sampler_scheduler_links import (
    apply_choice_selection,
    build_sampler_choice_items,
    build_scheduler_choice_items,
    resolve_linked_choice_label,
    sanitize_sampler_link_selection,
    sanitize_scheduler_link_selection,
    update_sampler_link_references_on_rename,
    update_scheduler_link_references_on_rename,
)

__all__ = [
    "apply_choice_selection",
    "build_sampler_choice_items",
    "build_scheduler_choice_items",
    "find_first_cube_with_prompt",
    "NodeLinkEndpoint",
    "NodeLinkEndpointIndex",
    "NodeLinkIdentity",
    "NodeLinkReference",
    "PromptEndpoint",
    "PromptEndpointIndex",
    "resolve_linked_choice_label",
    "sanitize_sampler_link_selection",
    "sanitize_scheduler_link_selection",
    "update_node_link_references_on_rename",
    "update_prompt_link_references_on_rename",
    "update_sampler_link_references_on_rename",
    "update_scheduler_link_references_on_rename",
    "valid_link_options",
]
