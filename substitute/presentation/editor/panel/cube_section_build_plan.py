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

"""Plan cube-section node-card build order and skipped-card outcomes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from substitute.application.node_behavior import ResolvedFieldSpec, order_node_cards


NodeCardBuildOutcomeKind = Literal[
    "built",
    "hidden_by_policy",
    "connection_only",
    "missing_behavior",
    "missing_field_specs",
    "factory_returned_none",
    "build_error",
]


@dataclass(frozen=True, slots=True)
class NodeCardBuildOutcome:
    """Describe how one cube node was accounted for during card projection."""

    node_name: str
    node_class_type: str
    kind: NodeCardBuildOutcomeKind
    field_spec_count: int
    message: str = ""


def node_card_build_outcome(
    *,
    node_name: str,
    node_class_type: str,
    kind: NodeCardBuildOutcomeKind,
    field_spec_count: int,
    message: str = "",
) -> NodeCardBuildOutcome:
    """Create one immutable skipped-or-built node-card outcome."""

    return NodeCardBuildOutcome(
        node_name=node_name,
        node_class_type=node_class_type,
        kind=kind,
        field_spec_count=field_spec_count,
        message=message,
    )


def node_order_for_cube(
    nodes: Mapping[str, object],
    field_specs_by_node: Mapping[str, Mapping[str, ResolvedFieldSpec]],
) -> list[str]:
    """Return field-spec order when available, otherwise Comfy node-card order."""

    if field_specs_by_node:
        return list(field_specs_by_node.keys())
    return order_node_cards(nodes)


def leading_first_usable_node_count(
    *,
    node_order: Sequence[str],
    cube: Mapping[str, object],
    behavior_snapshot: object,
    cube_alias: str,
) -> int:
    """Return the leading prompt-card count used for progressive readiness."""

    count = 0
    for node_name in node_order:
        if not is_first_usable_card(
            node_name,
            cube=cube,
            behavior_snapshot=behavior_snapshot,
            cube_alias=cube_alias,
        ):
            break
        count += 1
    return count


def is_first_usable_card(
    node_name: str,
    *,
    cube: Mapping[str, object],
    behavior_snapshot: object,
    cube_alias: str,
) -> bool:
    """Return whether one card belongs to the initial prompt editing set."""

    resolved_nodes = getattr(
        behavior_snapshot,
        "resolved_nodes_by_alias",
        {},
    )
    resolved_behavior = resolved_nodes.get(cube_alias, {}).get(node_name)
    card = getattr(resolved_behavior, "card", None)
    card_mode = getattr(card, "card_mode", None)
    if getattr(card_mode, "value", None) == "prompt":
        return True

    raw_nodes = cube.get("nodes", {})
    nodes = raw_nodes if isinstance(raw_nodes, Mapping) else {}
    node_data = nodes.get(node_name)
    node_type = ""
    if isinstance(node_data, Mapping):
        raw_type = node_data.get("class_type", "")
        node_type = str(raw_type).casefold()
    normalized_name = node_name.casefold()
    first_usable_terms = (
        "prompt",
        "cliptextencode",
    )
    return any(
        term in normalized_name or term in node_type for term in first_usable_terms
    )


def empty_card_outcome_kind(
    *,
    inputs: Mapping[str, object],
    field_specs: Mapping[str, ResolvedFieldSpec],
    display_decision: object | None,
) -> NodeCardBuildOutcomeKind:
    """Classify why a node-card builder returned no widget."""

    if display_decision is not None and not bool(
        getattr(display_decision, "visible", True)
    ):
        return "hidden_by_policy"
    if not field_specs:
        return "missing_field_specs"
    field_keys = tuple(field_specs.keys())
    if field_keys and all(
        is_connection_value(inputs.get(field_key)) for field_key in field_keys
    ):
        return "connection_only"
    return "factory_returned_none"


def is_connection_value(value: object) -> bool:
    """Return whether a cube input value represents a Comfy node connection."""

    return isinstance(value, list) and len(value) >= 1 and isinstance(value[0], str)
