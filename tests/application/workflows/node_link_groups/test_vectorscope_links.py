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

"""Vectorscope node link-group contracts."""

from __future__ import annotations


from tests.application.workflows.node_link_groups.support import (
    _cube_state,
    _node,
    _node_link_payload,
    _service,
)


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
