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

"""Verify domain hidden-field key merging."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.domain.links import NodeLinkEndpoint, NodeLinkEndpointIndex
from substitute.domain.node_behavior import compute_all_hidden_keys


def test_hidden_fields_merge_overrides_prompt_link_and_search() -> None:
    """Merge overrides, linked prompt fields, and search-hidden keys."""

    nodes_a = {
        "positive_prompt": {
            "class_type": "CSVWildcardNode",
            "inputs": {"prompt_template": "foo"},
            "node_link": {"from_cube": "B", "from_node": "positive_prompt"},
        },
        "KSampler": {
            "class_type": "KSampler",
            "inputs": {"sampler_name": "Euler", "scheduler": "normal"},
        },
    }
    cube_a = SimpleNamespace(buffer={"nodes": nodes_a}, ui=None)
    workflow_cubes = {"A": cube_a}

    overrides = {"sampler_name": {"value": "Euler a"}}
    search_hidden: set[object] = {"cfg"}

    hidden = compute_all_hidden_keys(
        overrides=overrides,
        cubes=workflow_cubes,
        node_link_endpoint_index=NodeLinkEndpointIndex.from_endpoints(
            (
                NodeLinkEndpoint(
                    cube_alias="A",
                    node_name="positive_prompt",
                    class_type="CSVWildcardNode",
                    family="prompt:positive",
                    editable_value_keys=("prompt_template",),
                ),
            )
        ),
        search_hidden_keys=search_hidden,
    )

    assert "sampler_name" in hidden
    assert ("A", "positive_prompt", "prompt_template") in hidden
    assert "cfg" in hidden
