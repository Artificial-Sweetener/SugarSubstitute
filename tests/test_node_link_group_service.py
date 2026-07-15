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

"""Contract tests for generic whole-node link group orchestration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Mapping, cast

from substitute.application.workflows import NodeLinkGroupService
from substitute.domain.links import NodeLinkEndpoint, NodeLinkEndpointIndex


class _NodeLinkEndpointProvider:
    """Build node-link endpoints for minimal service-test buffers."""

    _prompt_reset = {"value": ""}
    _vectorscope_keys = (
        "alt",
        "brightness",
        "contrast",
        "saturation",
        "r",
        "g",
        "b",
        "method",
        "scaling",
    )

    def build_node_link_endpoint_index(
        self,
        cube_states: Mapping[str, object],
        stack_order: list[str],
    ) -> NodeLinkEndpointIndex:
        """Return test endpoints for prompt and VectorscopeCC nodes."""

        endpoints: list[NodeLinkEndpoint] = []
        for cube_alias in stack_order:
            cube_state = cube_states.get(cube_alias)
            buffer = getattr(cube_state, "buffer", {})
            nodes = buffer.get("nodes", {}) if isinstance(buffer, dict) else {}
            if not isinstance(nodes, Mapping):
                continue
            prompt_node = nodes.get("positive_prompt")
            if isinstance(prompt_node, Mapping):
                endpoints.append(
                    NodeLinkEndpoint(
                        cube_alias=cube_alias,
                        node_name="positive_prompt",
                        class_type=str(prompt_node.get("class_type", "String")),
                        family="prompt:positive",
                        editable_value_keys=("value",),
                        reset_values=self._prompt_reset,
                    )
                )
            vectorscope_node = nodes.get("vectorscopecc")
            if isinstance(vectorscope_node, Mapping):
                endpoints.append(
                    NodeLinkEndpoint(
                        cube_alias=cube_alias,
                        node_name="vectorscopecc",
                        class_type=str(vectorscope_node.get("class_type", "")),
                        family="vectorscopecc",
                        editable_value_keys=self._vectorscope_keys,
                        graph_signature=self._graph_signature(vectorscope_node),
                    )
                )
        return NodeLinkEndpointIndex.from_endpoints(endpoints)

    @staticmethod
    def _graph_signature(
        node: Mapping[str, object],
    ) -> tuple[tuple[str, object], ...]:
        """Return a compact graph signature for connection-shaped test inputs."""

        inputs = node.get("inputs", {})
        if not isinstance(inputs, Mapping):
            return ()
        signature: list[tuple[str, object]] = []
        for key, value in inputs.items():
            if (
                isinstance(key, str)
                and isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], str)
                and isinstance(value[1], int)
            ):
                signature.append((key, (value[0], value[1])))
        return tuple(sorted(signature))


def _cube_state(buffer: dict[str, object]) -> SimpleNamespace:
    """Build a minimal cube-state test double exposing a mutable buffer."""

    return SimpleNamespace(buffer=buffer)


def _service() -> NodeLinkGroupService:
    """Return the node-link service with deterministic endpoint discovery."""

    return NodeLinkGroupService(_NodeLinkEndpointProvider())


def _node(
    class_type: str,
    inputs: dict[str, object],
    *,
    from_cube: str | None | object = ...,
    from_node: str | None = None,
) -> dict[str, object]:
    """Build one node payload with optional node-link metadata."""

    node: dict[str, object] = {"class_type": class_type, "inputs": dict(inputs)}
    if from_cube is not ...:
        node["node_link"] = {"from_cube": from_cube, "from_node": from_node}
    return node


def _node_link_payload(node: dict[str, object]) -> dict[str, object]:
    """Return the node-link payload for one node."""

    return cast(dict[str, object], node["node_link"])


def test_reconcile_transition_auto_links_new_prompt_node_to_upstream_anchor() -> None:
    """New compatible prompt nodes should auto-link to the first upstream prompt node."""

    service = _service()
    previous = {
        "A": _cube_state(
            {"nodes": {"positive_prompt": _node("String", {"value": "anchor"})}},
        )
    }
    current = {
        **previous,
        "B": _cube_state(
            {"nodes": {"positive_prompt": _node("String", {"value": "local"})}},
        ),
    }

    service.reconcile_transition(
        previous_cube_states=previous,
        previous_stack_order=["A"],
        current_cube_states=current,
        current_stack_order=["A", "B"],
    )

    linked_node = current["B"].buffer["nodes"]["positive_prompt"]
    assert _node_link_payload(linked_node) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
    assert linked_node["inputs"]["value"] == "local"


def test_manual_node_selection_preserves_local_values_until_unlinked() -> None:
    """Manual node-link selection should not erase dormant local values."""

    service = _service()
    cubes = {
        "A": _cube_state(
            {"nodes": {"positive_prompt": _node("String", {"value": "anchor"})}},
        ),
        "B": _cube_state(
            {"nodes": {"positive_prompt": _node("String", {"value": "local"})}},
        ),
    }
    identity = (
        _NodeLinkEndpointProvider()
        .build_node_link_endpoint_index(cubes, ["A", "B"])
        .identities_for_cube("B")[0]
    )

    service.apply_manual_selection(
        cube_states=cubes,
        stack_order=["A", "B"],
        cube_alias="B",
        identity=identity,
        from_cube="A",
        from_node="positive_prompt",
    )

    linked_node = cubes["B"].buffer["nodes"]["positive_prompt"]
    assert _node_link_payload(linked_node) == {
        "from_cube": "A",
        "from_node": "positive_prompt",
    }
    assert linked_node["inputs"]["value"] == "local"

    service.apply_manual_selection(
        cube_states=cubes,
        stack_order=["A", "B"],
        cube_alias="B",
        identity=identity,
        from_cube=None,
        from_node=None,
    )

    assert _node_link_payload(linked_node) == {"from_cube": None, "from_node": None}
    assert linked_node["inputs"]["value"] == "local"


def test_reconcile_transition_rebases_prompt_anchor_and_resets_followers() -> None:
    """Prompt-style reset values should preserve old anchor text across reorder."""

    service = _service()
    cubes = {
        "A": _cube_state(
            {"nodes": {"positive_prompt": _node("String", {"value": "shared"})}},
        ),
        "B": _cube_state(
            {
                "nodes": {
                    "positive_prompt": _node(
                        "String",
                        {"value": "dormant"},
                        from_cube="A",
                        from_node="positive_prompt",
                    )
                }
            },
        ),
    }

    service.reconcile_transition(
        previous_cube_states=cubes,
        previous_stack_order=["A", "B"],
        current_cube_states=cubes,
        current_stack_order=["B", "A"],
    )

    node_b = cubes["B"].buffer["nodes"]["positive_prompt"]
    node_a = cubes["A"].buffer["nodes"]["positive_prompt"]
    assert _node_link_payload(node_b) == {"from_cube": None, "from_node": None}
    assert node_b["inputs"]["value"] == "shared"
    assert _node_link_payload(node_a) == {
        "from_cube": "B",
        "from_node": "positive_prompt",
    }
    assert node_a["inputs"]["value"] == ""


def test_vectorscope_node_link_preserves_multiple_dormant_values() -> None:
    """Vectorscope-style endpoints should link as whole nodes without value resets."""

    service = _service()
    previous = {
        "A": _cube_state(
            {
                "nodes": {
                    "vectorscopecc": _node(
                        "VectorscopeCC",
                        {
                            "model": ["provider", 0],
                            "alt": True,
                            "brightness": 0.25,
                            "contrast": 0.1,
                            "saturation": 1,
                            "r": 0,
                            "g": 0,
                            "b": 0,
                            "method": "Straight Abs.",
                            "scaling": "Flat",
                        },
                    )
                }
            }
        )
    }
    current = {
        **previous,
        "B": _cube_state(
            {
                "nodes": {
                    "vectorscopecc": _node(
                        "VectorscopeCC",
                        {
                            "model": ["provider", 0],
                            "alt": False,
                            "brightness": 0.75,
                            "contrast": 0.9,
                            "saturation": 1,
                            "r": 0,
                            "g": 0,
                            "b": 0,
                            "method": "Straight Abs.",
                            "scaling": "Flat",
                        },
                    )
                }
            }
        ),
    }

    service.reconcile_transition(
        previous_cube_states=previous,
        previous_stack_order=["A"],
        current_cube_states=current,
        current_stack_order=["A", "B"],
    )

    linked_node = current["B"].buffer["nodes"]["vectorscopecc"]
    assert _node_link_payload(linked_node) == {
        "from_cube": "A",
        "from_node": "vectorscopecc",
    }
    assert linked_node["inputs"]["brightness"] == 0.75
    assert linked_node["inputs"]["contrast"] == 0.9


def test_reconcile_transition_links_batch_completed_downstream_vectorscope_node() -> (
    None
):
    """Batch completion should default-link no-intent nodes once upstream exists."""

    service = _service()
    previous = {
        "B": _cube_state(
            {
                "nodes": {
                    "vectorscopecc": _node(
                        "VectorscopeCC",
                        {"model": ["provider", 0], "brightness": 0.75},
                    )
                }
            }
        )
    }
    current = {
        "A": _cube_state(
            {
                "nodes": {
                    "vectorscopecc": _node(
                        "VectorscopeCC",
                        {"model": ["provider", 0], "brightness": 0.25},
                    )
                }
            }
        ),
        "B": previous["B"],
    }

    service.reconcile_transition(
        previous_cube_states=previous,
        previous_stack_order=["B"],
        current_cube_states=current,
        current_stack_order=["A", "B"],
    )

    linked_node = current["B"].buffer["nodes"]["vectorscopecc"]
    assert _node_link_payload(linked_node) == {
        "from_cube": "A",
        "from_node": "vectorscopecc",
    }
    assert linked_node["inputs"]["brightness"] == 0.75


def test_reconcile_transition_links_reordered_no_intent_vectorscope_node() -> None:
    """Reorder should default-link nodes that become downstream without user intent."""

    service = _service()
    cubes = {
        "A": _cube_state(
            {
                "nodes": {
                    "vectorscopecc": _node(
                        "VectorscopeCC",
                        {"model": ["provider", 0], "brightness": 0.25},
                    )
                }
            }
        ),
        "B": _cube_state(
            {
                "nodes": {
                    "vectorscopecc": _node(
                        "VectorscopeCC",
                        {"model": ["provider", 0], "brightness": 0.75},
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

    assert _node_link_payload(cubes["B"].buffer["nodes"]["vectorscopecc"]) == {
        "from_cube": "A",
        "from_node": "vectorscopecc",
    }


def test_reconcile_transition_preserves_explicit_independent_vectorscope_node() -> None:
    """Explicit independent metadata should block automatic default linking."""

    service = _service()
    cubes = {
        "A": _cube_state(
            {
                "nodes": {
                    "vectorscopecc": _node(
                        "VectorscopeCC",
                        {"model": ["provider", 0], "brightness": 0.25},
                    )
                }
            }
        ),
        "B": _cube_state(
            {
                "nodes": {
                    "vectorscopecc": _node(
                        "VectorscopeCC",
                        {"model": ["provider", 0], "brightness": 0.75},
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

    linked_node = cubes["B"].buffer["nodes"]["vectorscopecc"]
    assert _node_link_payload(linked_node) == {"from_cube": None, "from_node": None}
    assert linked_node["inputs"]["brightness"] == 0.75


def test_graph_signature_mismatch_keeps_vectorscope_nodes_independent() -> None:
    """Nodes with different graph connection shapes should not share link options."""

    service = _service()
    previous = {
        "A": _cube_state(
            {
                "nodes": {
                    "vectorscopecc": _node(
                        "VectorscopeCC",
                        {"model": ["provider_a", 0], "brightness": 0.25},
                    )
                }
            }
        )
    }
    current = {
        **previous,
        "B": _cube_state(
            {
                "nodes": {
                    "vectorscopecc": _node(
                        "VectorscopeCC",
                        {"model": ["provider_b", 0], "brightness": 0.75},
                    )
                }
            }
        ),
    }

    service.reconcile_transition(
        previous_cube_states=previous,
        previous_stack_order=["A"],
        current_cube_states=current,
        current_stack_order=["A", "B"],
    )

    assert "node_link" not in current["B"].buffer["nodes"]["vectorscopecc"]
