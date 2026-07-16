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

"""Define typed application-facing render models derived from node behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from substitute.domain.node_behavior import (
    FieldBehavior,
    NodeDisplayDecision,
    ResolvedNodeBehavior,
    RevealMenuEntry,
)
from substitute.domain.links.node_links import NodeLinkEndpointIndex
from substitute.domain.links.prompt_endpoints import PromptEndpointIndex


class FieldValueSource(StrEnum):
    """Enumerate why one resolved field ended up with its effective render value."""

    EXPLICIT = "explicit"
    AUTHORED_DEFAULT = "authored_default"
    LINKED = "linked"
    LIVE_DEFAULT = "live_default"
    FIRST_OPTION = "first_option"
    FUTURE_USER_DEFAULT = "future_user_default"
    NO_OPTIONS = "no_options"


@dataclass(frozen=True)
class ResolvedFieldSpec:
    """Describe one application-owned field render contract for cards and toolbar."""

    cube_alias: str
    node_name: str
    class_type: str
    field_key: str
    field_type: str | None
    constraints: dict[str, object]
    meta_info: dict[str, object]
    field_info: list[object] | None
    value: object
    field_behavior: FieldBehavior
    raw_value: object | None = None
    value_source: FieldValueSource = FieldValueSource.EXPLICIT


@dataclass(frozen=True)
class EditorBehaviorSnapshot:
    """Expose the complete behavior snapshot consumed by editor presentation code."""

    resolved_nodes_by_alias: dict[str, dict[str, ResolvedNodeBehavior]]
    field_specs_by_alias: dict[str, dict[str, dict[str, ResolvedFieldSpec]]]
    card_decisions_by_alias: dict[str, dict[str, NodeDisplayDecision]]
    hidden_field_keys_by_alias: dict[str, set[object]]
    reveal_entries_by_alias: dict[str, list[RevealMenuEntry]]
    prompt_endpoint_index: PromptEndpointIndex = field(
        default_factory=PromptEndpointIndex
    )
    node_link_endpoint_index: NodeLinkEndpointIndex = field(
        default_factory=NodeLinkEndpointIndex
    )


__all__ = ["EditorBehaviorSnapshot", "FieldValueSource", "ResolvedFieldSpec"]
