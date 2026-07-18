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

"""Verify unified post-resolution prompt-aware node-card ordering."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from substitute.application.node_behavior import (
    FieldValueSource,
    NodeCardOrderPlanner,
    NodeCardOrderRequest,
    NodeCardOrderingMode,
    ResolvedFieldSpec,
)
from substitute.domain.node_behavior import (
    FieldBehavior,
    NodeDisplayDecision,
    PromptFieldBehavior,
    PromptFieldLocator,
    PromptGraphContext,
    PromptRole,
)


def _context(
    anchor: str,
    *,
    positive: Sequence[str],
    negative: Sequence[str],
) -> PromptGraphContext:
    """Return one graph-anchored prompt context for node-owned text fields."""

    return PromptGraphContext(
        anchor_node_name=anchor,
        positive_fields=tuple(PromptFieldLocator(node, "text") for node in positive),
        negative_fields=tuple(PromptFieldLocator(node, "text") for node in negative),
    )


def _prompt_spec(node_name: str, role: PromptRole) -> ResolvedFieldSpec:
    """Return one resolved visible prompt field for planner fixtures."""

    return ResolvedFieldSpec(
        cube_alias="Section",
        node_name=node_name,
        class_type="PrimitiveNode",
        field_key="text",
        field_type="STRING",
        constraints={},
        meta_info={},
        field_info=None,
        value="prompt",
        field_behavior=FieldBehavior(
            field_key="text",
            prompt=PromptFieldBehavior(role=role),
        ),
        value_source=FieldValueSource.EXPLICIT,
    )


def _request(
    *,
    mode: NodeCardOrderingMode,
    baseline: Sequence[str],
    nodes: Mapping[str, object] | None = None,
    prompt_roles: Mapping[str, PromptRole],
    contexts: Sequence[PromptGraphContext] = (),
    hidden_nodes: frozenset[str] = frozenset(),
) -> NodeCardOrderRequest:
    """Return one complete resolved ordering request."""

    return NodeCardOrderRequest(
        mode=mode,
        baseline_order=tuple(baseline),
        nodes=nodes or {node_name: {"inputs": {}} for node_name in baseline},
        field_specs_by_node={
            node_name: {"text": _prompt_spec(node_name, role)}
            for node_name, role in prompt_roles.items()
        },
        card_decisions={
            node_name: NodeDisplayDecision(
                visible=node_name not in hidden_nodes,
                enabled=True,
                reason="fixture",
            )
            for node_name in baseline
        },
        prompt_contexts=tuple(contexts),
    )


def test_cube_places_all_prompt_contexts_and_unanchored_prompts_first() -> None:
    """A cube should treat itself as one authored prompt-first segment."""

    baseline = (
        "loader",
        "later_positive",
        "first_negative",
        "ordinary",
        "first_positive",
        "first_anchor",
        "later_negative",
        "later_anchor",
        "orphan_prompt",
    )
    request = _request(
        mode=NodeCardOrderingMode.CUBE,
        baseline=baseline,
        prompt_roles={
            "first_positive": PromptRole.POSITIVE,
            "first_negative": PromptRole.NEGATIVE,
            "later_positive": PromptRole.POSITIVE,
            "later_negative": PromptRole.NEGATIVE,
            "orphan_prompt": PromptRole.POSITIVE,
        },
        contexts=(
            _context(
                "later_anchor",
                positive=("later_positive",),
                negative=("later_negative",),
            ),
            _context(
                "first_anchor",
                positive=("first_positive",),
                negative=("first_negative",),
            ),
        ),
    )

    assert NodeCardOrderPlanner().plan(request) == (
        "first_positive",
        "first_negative",
        "later_positive",
        "later_negative",
        "orphan_prompt",
        "loader",
        "ordinary",
        "first_anchor",
        "later_anchor",
    )


def test_cube_orders_unanchored_positive_prompt_before_negative_prompt() -> None:
    """Resolved cube prompt roles must retain the positive-first contract."""

    request = _request(
        mode=NodeCardOrderingMode.CUBE,
        baseline=("loader", "negative_prompt", "positive_prompt", "sampler"),
        prompt_roles={
            "positive_prompt": PromptRole.POSITIVE,
            "negative_prompt": PromptRole.NEGATIVE,
        },
    )

    assert NodeCardOrderPlanner().plan(request) == (
        "positive_prompt",
        "negative_prompt",
        "loader",
        "sampler",
    )


def test_cube_preserves_baseline_order_for_multi_contributor_context() -> None:
    """Multiple contributors should preserve same-role order without role inversion."""

    baseline = ("positive_b", "negative", "loader", "positive_a", "anchor")
    request = _request(
        mode=NodeCardOrderingMode.CUBE,
        baseline=baseline,
        prompt_roles={
            "positive_a": PromptRole.POSITIVE,
            "positive_b": PromptRole.POSITIVE,
            "negative": PromptRole.NEGATIVE,
        },
        contexts=(
            _context(
                "anchor",
                positive=("positive_a", "positive_b"),
                negative=("negative",),
            ),
        ),
    )

    assert NodeCardOrderPlanner().plan(request) == (
        "positive_b",
        "positive_a",
        "negative",
        "loader",
        "anchor",
    )


def test_direct_workflow_opens_first_pair_and_moves_later_pair_to_stage_entry() -> None:
    """A sequential second pair should lead the graph slice after the first anchor."""

    baseline = (
        "loader",
        "negative_1",
        "positive_1",
        "negative_2",
        "positive_2",
        "encode_1_positive",
        "encode_1_negative",
        "anchor_1",
        "bridge",
        "encode_2_positive",
        "encode_2_negative",
        "anchor_2",
        "save",
    )
    nodes: dict[str, object] = {node_name: {"inputs": {}} for node_name in baseline}
    nodes["encode_1_positive"] = {"inputs": {"text": ["positive_1", 0]}}
    nodes["encode_1_negative"] = {"inputs": {"text": ["negative_1", 0]}}
    nodes["anchor_1"] = {
        "inputs": {
            "positive": ["encode_1_positive", 0],
            "negative": ["encode_1_negative", 0],
        }
    }
    nodes["bridge"] = {"inputs": {"image": ["anchor_1", 0]}}
    nodes["encode_2_positive"] = {"inputs": {"text": ["positive_2", 0]}}
    nodes["encode_2_negative"] = {"inputs": {"text": ["negative_2", 0]}}
    nodes["anchor_2"] = {
        "inputs": {
            "image": ["bridge", 0],
            "positive": ["encode_2_positive", 0],
            "negative": ["encode_2_negative", 0],
        }
    }
    nodes["save"] = {"inputs": {"image": ["anchor_2", 0]}}
    request = _request(
        mode=NodeCardOrderingMode.DIRECT_WORKFLOW,
        baseline=baseline,
        nodes=nodes,
        prompt_roles={
            "positive_1": PromptRole.POSITIVE,
            "negative_1": PromptRole.NEGATIVE,
            "positive_2": PromptRole.POSITIVE,
            "negative_2": PromptRole.NEGATIVE,
        },
        contexts=(
            _context(
                "anchor_1",
                positive=("positive_1",),
                negative=("negative_1",),
            ),
            _context(
                "anchor_2",
                positive=("positive_2",),
                negative=("negative_2",),
            ),
        ),
    )

    assert NodeCardOrderPlanner().plan(request) == (
        "positive_1",
        "negative_1",
        "loader",
        "encode_1_positive",
        "encode_1_negative",
        "anchor_1",
        "positive_2",
        "negative_2",
        "bridge",
        "encode_2_positive",
        "encode_2_negative",
        "anchor_2",
        "save",
    )


def test_independent_direct_context_moves_only_immediately_before_its_anchor() -> None:
    """Independent branches should retain context without inventing a shared segment."""

    baseline = (
        "positive_1",
        "negative_1",
        "positive_2",
        "negative_2",
        "branch_1_control",
        "anchor_1",
        "branch_2_control",
        "anchor_2",
    )
    nodes: dict[str, object] = {node_name: {"inputs": {}} for node_name in baseline}
    nodes["anchor_1"] = {"inputs": {"control": ["branch_1_control", 0]}}
    nodes["anchor_2"] = {"inputs": {"control": ["branch_2_control", 0]}}
    request = _request(
        mode=NodeCardOrderingMode.DIRECT_WORKFLOW,
        baseline=baseline,
        nodes=nodes,
        prompt_roles={
            "positive_1": PromptRole.POSITIVE,
            "negative_1": PromptRole.NEGATIVE,
            "positive_2": PromptRole.POSITIVE,
            "negative_2": PromptRole.NEGATIVE,
        },
        contexts=(
            _context(
                "anchor_1",
                positive=("positive_1",),
                negative=("negative_1",),
            ),
            _context(
                "anchor_2",
                positive=("positive_2",),
                negative=("negative_2",),
            ),
        ),
    )

    assert NodeCardOrderPlanner().plan(request) == (
        "positive_1",
        "negative_1",
        "branch_1_control",
        "anchor_1",
        "branch_2_control",
        "positive_2",
        "negative_2",
        "anchor_2",
    )


def test_direct_unanchored_prompts_retain_baseline_position() -> None:
    """Authored prompt behavior alone should not create a workflow segment."""

    baseline = ("loader", "authored_positive", "ordinary")
    request = _request(
        mode=NodeCardOrderingMode.DIRECT_WORKFLOW,
        baseline=baseline,
        prompt_roles={"authored_positive": PromptRole.POSITIVE},
    )

    assert NodeCardOrderPlanner().plan(request) == baseline


def test_direct_literal_pair_keeps_explicit_opening_contract_without_anchor() -> None:
    """The authoritative literal pair should remain a supported opening fallback."""

    baseline = ("loader", "negative_prompt", "ordinary", "positive_prompt")
    request = _request(
        mode=NodeCardOrderingMode.DIRECT_WORKFLOW,
        baseline=baseline,
        prompt_roles={
            "positive_prompt": PromptRole.POSITIVE,
            "negative_prompt": PromptRole.NEGATIVE,
        },
    )

    assert NodeCardOrderPlanner().plan(request) == (
        "positive_prompt",
        "negative_prompt",
        "loader",
        "ordinary",
    )


def test_hidden_prompt_is_not_promoted_or_used_to_form_an_opening_pair() -> None:
    """Ordering must not make a policy-hidden prompt visually significant."""

    baseline = ("loader", "negative", "positive", "anchor")
    request = _request(
        mode=NodeCardOrderingMode.CUBE,
        baseline=baseline,
        prompt_roles={
            "positive": PromptRole.POSITIVE,
            "negative": PromptRole.NEGATIVE,
        },
        contexts=(
            _context(
                "anchor",
                positive=("positive",),
                negative=("negative",),
            ),
        ),
        hidden_nodes=frozenset({"negative"}),
    )

    assert NodeCardOrderPlanner().plan(request) == (
        "positive",
        "loader",
        "negative",
        "anchor",
    )
