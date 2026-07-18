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

"""Project resolved prompt fields into renderable node-card semantics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from substitute.domain.node_behavior import (
    NodeDisplayDecision,
    PromptFieldLocator,
    PromptGraphContext,
    PromptRole,
)

from .models import ResolvedFieldSpec


def renderable_prompt_roles(
    *,
    baseline_order: Sequence[str],
    nodes: Mapping[str, object],
    field_specs_by_node: Mapping[str, Mapping[str, ResolvedFieldSpec]],
    card_decisions: Mapping[str, NodeDisplayDecision],
) -> dict[str, PromptRole]:
    """Return prompt roles that survive final field and card visibility rules."""

    roles: dict[str, PromptRole] = {}
    for node_name in baseline_order:
        decision = card_decisions.get(node_name)
        if decision is not None and not decision.visible:
            continue
        node_data = nodes.get(node_name)
        inputs = node_data.get("inputs", {}) if isinstance(node_data, Mapping) else {}
        input_values = inputs if isinstance(inputs, Mapping) else {}
        node_roles = {
            prompt.role
            for field_key, field_spec in field_specs_by_node.get(node_name, {}).items()
            if not field_spec.field_behavior.hidden
            and (prompt := field_spec.field_behavior.prompt) is not None
            and not _is_node_link(input_values.get(field_key))
        }
        if len(node_roles) == 1:
            roles[node_name] = next(iter(node_roles))
    return roles


def prompt_nodes_for_context(
    context: PromptGraphContext,
    baseline_order: Sequence[str],
    prompt_roles: Mapping[str, PromptRole],
) -> tuple[str, ...]:
    """Return visible context members in positive-then-negative role order."""

    positive = _unique_nodes(context.positive_fields, prompt_roles, PromptRole.POSITIVE)
    negative = _unique_nodes(context.negative_fields, prompt_roles, PromptRole.NEGATIVE)
    members = set(positive + negative)
    return prompt_nodes_in_role_order(
        tuple(node_name for node_name in baseline_order if node_name in members),
        prompt_roles,
    )


def prompt_nodes_in_role_order(
    node_names: Sequence[str],
    prompt_roles: Mapping[str, PromptRole],
) -> tuple[str, ...]:
    """Return prompt nodes positive-first while preserving order within each role."""

    return tuple(
        node_name
        for role in (PromptRole.POSITIVE, PromptRole.NEGATIVE)
        for node_name in node_names
        if prompt_roles.get(node_name) is role
    )


def literal_prompt_pair(prompt_roles: Mapping[str, PromptRole]) -> tuple[str, ...]:
    """Return the explicit legacy pair when both prompt aliases are renderable."""

    if (
        prompt_roles.get("positive_prompt") is PromptRole.POSITIVE
        and prompt_roles.get("negative_prompt") is PromptRole.NEGATIVE
    ):
        return ("positive_prompt", "negative_prompt")
    return ()


def is_exact_prompt_pair(
    node_names: Sequence[str],
    prompt_roles: Mapping[str, PromptRole],
) -> bool:
    """Return whether nodes contain exactly one positive and one negative card."""

    return len(node_names) == 2 and tuple(
        prompt_roles[node_name] for node_name in node_names
    ) == (PromptRole.POSITIVE, PromptRole.NEGATIVE)


def _unique_nodes(
    locators: Sequence[PromptFieldLocator],
    prompt_roles: Mapping[str, PromptRole],
    role: PromptRole,
) -> tuple[str, ...]:
    """Return unique locator owners whose resolved prompt role still matches."""

    nodes: list[str] = []
    for locator in locators:
        if (
            prompt_roles.get(locator.node_name) is role
            and locator.node_name not in nodes
        ):
            nodes.append(locator.node_name)
    return tuple(nodes)


def _is_node_link(value: object) -> bool:
    """Return whether a field value is supplied by another graph node."""

    return (
        isinstance(value, list) and len(value) >= 1 and isinstance(value[0], str | int)
    )


__all__ = [
    "is_exact_prompt_pair",
    "literal_prompt_pair",
    "prompt_nodes_in_role_order",
    "prompt_nodes_for_context",
    "renderable_prompt_roles",
]
