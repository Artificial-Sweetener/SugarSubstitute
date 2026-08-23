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

"""Behavior snapshot display-label contracts."""

from __future__ import annotations

from pathlib import Path


from substitute.domain.comfy_workflow import DirectWorkflowState
from tests.support.node_behavior import (
    build_behavior_snapshot,
    cube_state,
)
from tests.application.node_behavior.service.support import (
    _wrapper_live_definitions,
)


def test_normal_cube_node_key_owns_formatted_card_display_label() -> None:
    """SugarCube node keys should outrank raw Comfy titles as card identities."""

    cube = cube_state(
        nodes={
            "mahiro_cfg": {
                "class_type": "MahiroCFG",
                "inputs": {},
                "_meta": {"title": "mahiro CFG"},
            },
            "vectorscopeCC": {
                "class_type": "VectorscopeCC",
                "inputs": {},
                "_meta": {"title": "vectorscopeCC"},
            },
            "positive_prompt": {
                "class_type": "UnavailableStringNode",
                "inputs": {"value": "a red fox"},
            },
        },
        definitions={
            "MahiroCFG": {"input": {"required": {}}},
            "VectorscopeCC": {"input": {"required": {}}},
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_wrapper_live_definitions(),
    )

    assert (
        snapshot.resolved_nodes_by_alias["A"]["mahiro_cfg"].display_name == "Mahiro CFG"
    )
    assert (
        snapshot.resolved_nodes_by_alias["A"]["vectorscopeCC"].display_name
        == "VectorscopeCC"
    )
    assert (
        snapshot.resolved_nodes_by_alias["A"]["positive_prompt"].display_name
        == "Positive Prompt"
    )


def test_direct_workflow_node_title_owns_card_display_label() -> None:
    """Direct graphs should display preserved titles instead of numeric node ids."""

    direct = DirectWorkflowState(
        source_path=Path("workflow.json"),
        source_workflow={"nodes": [], "links": []},
        buffer={
            "nodes": {
                "20": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {},
                    "_meta": {"title": "  Load model  "},
                },
                "14": {
                    "class_type": "KSamplerSelect",
                    "inputs": {},
                    "_meta": {"title": "KSamplerSelect"},
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"Direct": direct},
        stack_order=["Direct"],
    )

    resolved = snapshot.resolved_nodes_by_alias["Direct"]
    assert resolved["20"].display_name == "  Load model  "
    assert resolved["14"].display_name == "KSamplerSelect"
