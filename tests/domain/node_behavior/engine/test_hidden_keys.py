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

"""Verify merged hidden-key engine policy."""

from __future__ import annotations

from substitute.domain.links import NodeLinkEndpoint, NodeLinkEndpointIndex
from substitute.domain.node_behavior import compute_all_hidden_keys
from substitute.domain.workflow import CubeState, WorkflowState


def test_compute_all_hidden_keys_merges_overrides_links_and_search() -> None:
    """Merge override, active node-link, and search-hidden key sources."""

    cube_buffer: dict[str, object] = {
        "cube_id": "Text To Image",
        "nodes": {
            "positive_prompt": {
                "inputs": {"prompt_template": ""},
                "node_link": {"from_cube": "Other", "from_node": "positive_prompt"},
            }
        },
    }
    cube_state = CubeState(
        cube_id="Text To Image",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer=cube_buffer,
    )
    workflow = WorkflowState(cubes={"A": cube_state}, stack_order=["A"])

    hidden = compute_all_hidden_keys(
        overrides={"seed": {"value": 123}},
        cubes=workflow.cubes,
        node_link_endpoint_index=NodeLinkEndpointIndex.from_endpoints(
            (
                NodeLinkEndpoint(
                    cube_alias="A",
                    node_name="positive_prompt",
                    class_type="PrimitiveStringMultiline",
                    family="prompt:positive",
                    editable_value_keys=("prompt_template",),
                ),
            )
        ),
        search_hidden_keys={("Z", "node", "field")},
    )

    assert "seed" in hidden
    assert ("A", "positive_prompt", "prompt_template") in hidden
    assert ("Z", "node", "field") in hidden
