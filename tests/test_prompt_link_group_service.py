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

"""Contract tests for prompt-link group orchestration and transition semantics."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Mapping, cast

from substitute.application.workflows import PromptLinkGroupService
from substitute.domain.links import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole


class _PromptEndpointProvider:
    """Build prompt endpoints for the minimal buffers used by service tests."""

    _endpoint_specs = {
        "positive_prompt": ("prompt_template", PromptRole.POSITIVE),
        "negative_prompt": ("prompt_template", PromptRole.NEGATIVE),
        "custom_positive": ("text", PromptRole.POSITIVE),
    }

    def build_prompt_endpoint_index(
        self,
        cube_states: Mapping[str, object],
        stack_order: list[str],
    ) -> PromptEndpointIndex:
        """Return endpoints for known prompt nodes in stack order."""

        endpoints: list[PromptEndpoint] = []
        for cube_alias in stack_order:
            cube_state = cube_states.get(cube_alias)
            buffer = getattr(cube_state, "buffer", {})
            nodes = buffer.get("nodes", {}) if isinstance(buffer, dict) else {}
            if not isinstance(nodes, Mapping):
                continue
            for node_name, (field_key, role) in self._endpoint_specs.items():
                if node_name in nodes:
                    endpoints.append(
                        PromptEndpoint(
                            cube_alias=cube_alias,
                            role=role,
                            node_name=node_name,
                            field_key=field_key,
                        )
                    )
        return PromptEndpointIndex.from_endpoints(endpoints)


def _cube_state(buffer: dict[str, object]) -> SimpleNamespace:
    """Build a minimal cube-state test double exposing a mutable buffer."""

    return SimpleNamespace(buffer=buffer)


def _service() -> PromptLinkGroupService:
    """Return the prompt-link service with a deterministic endpoint provider."""

    return PromptLinkGroupService(_PromptEndpointProvider())


def _prompt_node(
    prompt_template: str,
    *,
    from_cube: str | None | object = ...,
    from_node: str | None = "positive_prompt",
    field_key: str = "prompt_template",
    legacy: bool = False,
) -> dict[str, object]:
    """Build one prompt node payload with optional node-link metadata."""

    node: dict[str, object] = {"inputs": {field_key: prompt_template}}
    if from_cube is not ...:
        if legacy:
            node["prompt_link"] = {"from_cube": from_cube}
        else:
            node["node_link"] = {"from_cube": from_cube, "from_node": from_node}
    return node


def _link_payload(node: dict[str, object]) -> dict[str, object]:
    """Return the canonical node-link payload for one prompt node."""

    return cast(dict[str, object], node["node_link"])


def _prompt_text(node: dict[str, object], field_key: str = "prompt_template") -> str:
    """Return the local prompt text stored on one prompt node."""

    inputs = cast(dict[str, object], node["inputs"])
    return cast(str, inputs[field_key])


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


def test_apply_manual_selection_preserves_local_prompt_until_unlinked() -> None:
    """Manual prompt-link selection should not erase local prompt experimentation state."""

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

    service.apply_manual_selection(
        cube_states=cubes,
        stack_order=["A", "B"],
        cube_alias="B",
        role=PromptRole.POSITIVE,
        from_cube="A",
    )

    linked_node = cubes["B"].buffer["nodes"]["positive_prompt"]
    assert _link_payload(linked_node) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
    assert _prompt_text(linked_node) == "local"

    service.apply_manual_selection(
        cube_states=cubes,
        stack_order=["A", "B"],
        cube_alias="B",
        role=PromptRole.POSITIVE,
        from_cube=None,
    )

    assert _link_payload(linked_node) == {"from_cube": None, "from_node": None}
    assert _prompt_text(linked_node) == "local"


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


def test_sanitize_current_state_collapses_multi_hop_and_clears_invalid_links() -> None:
    """Normalization should rewrite multi-hop links to the anchor and clear illegal links."""

    service = _service()
    cubes = {
        "A": _cube_state({"nodes": {"positive_prompt": _prompt_node("anchor")}}),
        "B": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("beta", from_cube="A")}},
        ),
        "C": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("gamma", from_cube="B")}},
        ),
        "D": _cube_state(
            {"nodes": {"positive_prompt": _prompt_node("delta", from_cube="Z")}},
        ),
    }

    service.sanitize_current_state(cubes, ["A", "B", "C", "D"])

    assert _link_payload(cubes["B"].buffer["nodes"]["positive_prompt"]) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
    assert _link_payload(cubes["C"].buffer["nodes"]["positive_prompt"]) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
    assert _link_payload(cubes["D"].buffer["nodes"]["positive_prompt"]) == {
        "from_cube": None,
        "from_node": None,
    }


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


def test_sanitize_current_state_migrates_legacy_prompt_link_metadata() -> None:
    """Legacy prompt-link payloads should become canonical node-link payloads."""

    service = _service()
    cubes = {
        "A": _cube_state({"nodes": {"positive_prompt": _prompt_node("anchor")}}),
        "B": _cube_state(
            {
                "nodes": {
                    "positive_prompt": _prompt_node(
                        "local",
                        from_cube="A",
                        legacy=True,
                    )
                }
            }
        ),
    }

    service.sanitize_current_state(cubes, ["A", "B"])

    linked_node = cubes["B"].buffer["nodes"]["positive_prompt"]
    assert "prompt_link" not in linked_node
    assert _link_payload(linked_node) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
