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

"""Prompt-link transition reconciliation contracts."""

from __future__ import annotations

from tests.application.workflows.prompt_link_groups.support import (
    _cube_state,
    _link_payload,
    _prompt_node,
    _prompt_text,
    _service,
)


def test_reconcile_transition_auto_links_new_cube_to_first_earlier_prompt_owner() -> (
    None
):
    """Newly added prompt cubes should auto-link to the first earlier prompt cube."""

    service = _service()
    previous = {
        "A": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("alpha")}},
        ),
        "B": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("beta", from_cube="A")}},
        ),
    }
    current = {
        **previous,
        "C": _cube_state(
            {
                "nodes": {
                    "positive_prompt": _prompt_node("gamma"),
                    "negative_prompt": _prompt_node("neg-gamma"),
                }
            }
        ),
    }

    service.reconcile_transition(
        previous_cube_states=previous,
        previous_stack_order=["A", "B"],
        current_cube_states=current,
        current_stack_order=["A", "B", "C"],
    )

    positive_link = current["C"].buffer["nodes"]["positive_prompt"]["node_link"]
    negative_node = current["C"].buffer["nodes"]["negative_prompt"]
    assert positive_link == {"from_cube": "A", "from_node": "positive_prompt"}
    assert "node_link" not in negative_node
    assert (
        current["C"].buffer["nodes"]["positive_prompt"]["inputs"]["prompt_template"]
        == "gamma"
    )


def test_reconcile_transition_rebases_anchor_on_crossing_reorder() -> None:
    """Anchor-crossing reorder should preserve the shared prompt and discard dormant locals."""

    service = _service()
    previous = {
        "A": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("shared")}},
        ),
        "B": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("dormant", from_cube="A")}},
        ),
    }
    current = previous

    service.reconcile_transition(
        previous_cube_states=previous,
        previous_stack_order=["A", "B"],
        current_cube_states=current,
        current_stack_order=["B", "A"],
    )

    node_b = current["B"].buffer["nodes"]["positive_prompt"]
    node_a = current["A"].buffer["nodes"]["positive_prompt"]
    assert _link_payload(node_b) == {"from_cube": None, "from_node": None}
    assert _prompt_text(node_b) == "shared"
    assert _link_payload(node_a) == {
        "from_cube": "B",
        "from_node": "positive_prompt",
    }
    assert _prompt_text(node_a) == ""


def test_reconcile_transition_preserves_dormant_locals_when_anchor_unchanged() -> None:
    """Follower-only reorders should not commit or delete dormant local prompts."""

    service = _service()
    previous = {
        "A": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("shared")}},
        ),
        "B": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("beta-local", from_cube="A")}},
        ),
        "C": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("gamma-local", from_cube="A")}},
        ),
    }
    current = previous

    service.reconcile_transition(
        previous_cube_states=previous,
        previous_stack_order=["A", "B", "C"],
        current_cube_states=current,
        current_stack_order=["A", "C", "B"],
    )

    assert _prompt_text(current["A"].buffer["nodes"]["positive_prompt"]) == "shared"
    assert _prompt_text(current["B"].buffer["nodes"]["positive_prompt"]) == "beta-local"
    assert (
        _prompt_text(current["C"].buffer["nodes"]["positive_prompt"]) == "gamma-local"
    )
    assert _link_payload(current["B"].buffer["nodes"]["positive_prompt"]) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
    assert _link_payload(current["C"].buffer["nodes"]["positive_prompt"]) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }


def test_reconcile_transition_promotes_new_anchor_when_old_anchor_is_removed() -> None:
    """Anchor removal should promote the earliest remaining member and preserve the shared prompt."""

    service = _service()
    previous = {
        "A": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("shared")}},
        ),
        "B": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("beta-local", from_cube="A")}},
        ),
        "C": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("gamma-local", from_cube="A")}},
        ),
    }
    current = {
        "B": previous["B"],
        "C": previous["C"],
    }

    service.reconcile_transition(
        previous_cube_states=previous,
        previous_stack_order=["A", "B", "C"],
        current_cube_states=current,
        current_stack_order=["B", "C"],
    )

    node_b = current["B"].buffer["nodes"]["positive_prompt"]
    node_c = current["C"].buffer["nodes"]["positive_prompt"]
    assert _link_payload(node_b) == {"from_cube": None, "from_node": None}
    assert _prompt_text(node_b) == "shared"
    assert _link_payload(node_c) == {
        "from_cube": "B",
        "from_node": "positive_prompt",
    }
    assert _prompt_text(node_c) == "gamma-local"


def test_reconcile_transition_links_batch_completed_downstream_prompt_node() -> None:
    """Batch completion should default-link no-intent prompts once upstream exists."""

    service = _service()
    previous = {
        "B": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("local")}},
        )
    }
    current = {
        "A": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("anchor")}},
        ),
        "B": previous["B"],
    }

    service.reconcile_transition(
        previous_cube_states=previous,
        previous_stack_order=["B"],
        current_cube_states=current,
        current_stack_order=["A", "B"],
    )

    linked_node = current["B"].buffer["nodes"]["positive_prompt"]
    assert _link_payload(linked_node) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
    assert _prompt_text(linked_node) == "local"


def test_reconcile_transition_links_reordered_no_intent_prompt_node() -> None:
    """Reorder should default-link prompt nodes that become downstream."""

    service = _service()
    cubes = {
        "A": _cube_state({"nodes": {"positive_prompt": _prompt_node("anchor")}}),
        "B": _cube_state({"nodes": {"positive_prompt": _prompt_node("local")}}),
    }

    service.reconcile_transition(
        previous_cube_states=cubes,
        previous_stack_order=["B", "A"],
        current_cube_states=cubes,
        current_stack_order=["A", "B"],
    )

    assert _link_payload(cubes["B"].buffer["nodes"]["positive_prompt"]) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
    assert _prompt_text(cubes["B"].buffer["nodes"]["positive_prompt"]) == "local"


def test_reconcile_transition_preserves_explicit_independent_prompt_node() -> None:
    """Explicit independent prompt metadata should block automatic default linking."""

    service = _service()
    cubes = {
        "A": _cube_state({"nodes": {"positive_prompt": _prompt_node("anchor")}}),
        "B": _cube_state(
            {
                "nodes": {
                    "positive_prompt": _prompt_node(
                        "local",
                        from_cube=None,
                        from_node=None,
                    )
                }
            }
        ),
    }

    service.reconcile_transition(
        previous_cube_states=cubes,
        previous_stack_order=["B", "A"],
        current_cube_states=cubes,
        current_stack_order=["A", "B"],
    )

    linked_node = cubes["B"].buffer["nodes"]["positive_prompt"]
    assert _link_payload(linked_node) == {"from_cube": None, "from_node": None}
    assert _prompt_text(linked_node) == "local"


def test_prompt_link_service_uses_endpoint_node_and_field_for_generalized_prompts() -> (
    None
):
    """Role-based linking should not require legacy prompt node or field names."""

    service = _service()
    previous = {
        "A": _cube_state(
            {"nodes": {"custom_positive": _prompt_node("anchor", field_key="text")}}
        ),
    }
    current = {
        **previous,
        "B": _cube_state(
            {"nodes": {"custom_positive": _prompt_node("local", field_key="text")}}
        ),
    }

    service.reconcile_transition(
        previous_cube_states=previous,
        previous_stack_order=["A"],
        current_cube_states=current,
        current_stack_order=["A", "B"],
    )

    node_b = current["B"].buffer["nodes"]["custom_positive"]
    assert _link_payload(node_b) == {
        "from_cube": "A",
        "from_node": "custom_positive",
    }
    assert _prompt_text(node_b, "text") == "local"
