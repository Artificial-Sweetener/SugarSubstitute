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

"""Plan prompt-aware card order after behavior and visibility resolution."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from substitute.domain.node_behavior import (
    NodeDisplayDecision,
    PromptGraphContext,
    PromptRole,
)

from .models import ResolvedFieldSpec
from .node_card_order import downstream_node_graph, node_reaches
from .prompt_card_projection import (
    is_exact_prompt_pair,
    literal_prompt_pair,
    prompt_nodes_in_role_order,
    prompt_nodes_for_context,
    renderable_prompt_roles,
)


class NodeCardOrderingMode(StrEnum):
    """Select the product ordering policy for one editor graph section."""

    CUBE = "cube"
    DIRECT_WORKFLOW = "direct_workflow"


@dataclass(frozen=True, slots=True)
class NodeCardOrderRequest:
    """Carry resolved section state required for deterministic card ordering."""

    mode: NodeCardOrderingMode
    baseline_order: tuple[str, ...]
    nodes: Mapping[str, object]
    field_specs_by_node: Mapping[str, Mapping[str, ResolvedFieldSpec]]
    card_decisions: Mapping[str, NodeDisplayDecision]
    prompt_contexts: tuple[PromptGraphContext, ...]


class NodeCardOrderPlanner:
    """Apply cube or workflow prompt priority without owning graph semantics."""

    def plan(self, request: NodeCardOrderRequest) -> tuple[str, ...]:
        """Return one stable order for the existing shared card build session."""

        prompt_roles = renderable_prompt_roles(
            baseline_order=request.baseline_order,
            nodes=request.nodes,
            field_specs_by_node=request.field_specs_by_node,
            card_decisions=request.card_decisions,
        )
        contexts = _ordered_contexts(request.prompt_contexts, request.baseline_order)
        if request.mode is NodeCardOrderingMode.CUBE:
            return _cube_order(request.baseline_order, prompt_roles, contexts)
        return _direct_workflow_order(request, prompt_roles, contexts)


def _ordered_contexts(
    contexts: Sequence[PromptGraphContext],
    baseline_order: Sequence[str],
) -> tuple[PromptGraphContext, ...]:
    """Return reliable contexts in deterministic anchor chronology."""

    indexes = {node_name: index for index, node_name in enumerate(baseline_order)}
    return tuple(
        sorted(
            contexts,
            key=lambda context: (
                indexes.get(context.anchor_node_name, len(indexes)),
                context.anchor_node_name,
            ),
        )
    )


def _cube_order(
    baseline_order: Sequence[str],
    prompt_roles: Mapping[str, PromptRole],
    contexts: Sequence[PromptGraphContext],
) -> tuple[str, ...]:
    """Place every visible cube prompt before unchanged-order ordinary cards."""

    prompt_nodes: list[str] = []
    for context in contexts:
        _extend_unique(
            prompt_nodes,
            prompt_nodes_for_context(context, baseline_order, prompt_roles),
        )
    _extend_unique(
        prompt_nodes,
        prompt_nodes_in_role_order(baseline_order, prompt_roles),
    )
    return tuple(prompt_nodes) + tuple(
        node_name for node_name in baseline_order if node_name not in prompt_nodes
    )


def _direct_workflow_order(
    request: NodeCardOrderRequest,
    prompt_roles: Mapping[str, PromptRole],
    contexts: Sequence[PromptGraphContext],
) -> tuple[str, ...]:
    """Open with one exact pair and keep later prompt contexts near their stage."""

    context_nodes = [
        prompt_nodes_for_context(context, request.baseline_order, prompt_roles)
        for context in contexts
    ]
    opening_index = next(
        (
            index
            for index, nodes in enumerate(context_nodes)
            if is_exact_prompt_pair(nodes, prompt_roles)
        ),
        None,
    )
    opening_nodes = (
        context_nodes[opening_index]
        if opening_index is not None
        else literal_prompt_pair(prompt_roles)
    )
    ordered = list(opening_nodes) + [
        node_name
        for node_name in request.baseline_order
        if node_name not in opening_nodes
    ]
    moved = set(opening_nodes)
    graph = downstream_node_graph(request.nodes)
    for index, context in enumerate(contexts):
        if index == opening_index:
            continue
        nodes_to_move = [node for node in context_nodes[index] if node not in moved]
        if not nodes_to_move:
            continue
        ordered = [node for node in ordered if node not in nodes_to_move]
        target = _segment_entry_node(
            context_index=index,
            contexts=contexts,
            baseline_order=request.baseline_order,
            graph=graph,
            prompt_nodes=frozenset(prompt_roles),
        )
        insertion_index = ordered.index(target) if target in ordered else len(ordered)
        ordered[insertion_index:insertion_index] = nodes_to_move
        moved.update(nodes_to_move)
    return tuple(ordered)


def _segment_entry_node(
    *,
    context_index: int,
    contexts: Sequence[PromptGraphContext],
    baseline_order: Sequence[str],
    graph: Mapping[str, tuple[str, ...]],
    prompt_nodes: frozenset[str],
) -> str:
    """Return a topology-supported entry for one non-opening prompt context."""

    current_anchor = contexts[context_index].anchor_node_name
    if context_index == 0:
        return current_anchor
    previous_anchor = contexts[context_index - 1].anchor_node_name
    if not node_reaches(graph, previous_anchor, current_anchor):
        return current_anchor
    previous_index = baseline_order.index(previous_anchor)
    return next(
        (
            node_name
            for node_name in baseline_order[previous_index + 1 :]
            if node_name not in prompt_nodes
            and node_reaches(graph, node_name, current_anchor)
        ),
        current_anchor,
    )


def _extend_unique(target: list[str], values: Iterable[str]) -> None:
    """Append stable node identities not already present in target."""

    for value in values:
        if value not in target:
            target.append(value)


__all__ = [
    "NodeCardOrderPlanner",
    "NodeCardOrderRequest",
    "NodeCardOrderingMode",
]
