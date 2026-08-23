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

"""Prompt node link-group contracts."""

from __future__ import annotations


from tests.application.workflows.node_link_groups.support import (
    _NodeLinkEndpointProvider,
    _cube_state,
    _node,
    _node_link_payload,
    _service,
)


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
