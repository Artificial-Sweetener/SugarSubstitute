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

"""Verify behavior snapshots own final cube and direct-workflow card order."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.comfy_workflow import DirectWorkflowState
from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state


_DEFINITIONS: dict[str, dict[str, object]] = {
    "PromptValue": {
        "input": {"required": {"text": ["STRING", {"multiline": True}]}},
        "output": ["STRING"],
    },
    "UnknownEncoder": {
        "input": {"required": {"text": ["STRING", {}]}},
        "output": ["CONDITIONING"],
    },
    "Stage": {
        "input": {
            "required": {
                "positive": ["CONDITIONING", {}],
                "negative": ["CONDITIONING", {}],
            },
            "optional": {"image": ["IMAGE", {}]},
        },
        "output": ["IMAGE"],
    },
    "Bridge": {
        "input": {"required": {"image": ["IMAGE", {}]}},
        "output": ["IMAGE"],
    },
    "Ordinary": {
        "input": {"required": {"value": ["INT", {"default": 1}]}},
    },
}


def _two_stage_nodes() -> dict[str, object]:
    """Return a graph whose second prompt pair belongs to a later image stage."""

    return {
        "ordinary": {"class_type": "Ordinary", "inputs": {"value": 1}},
        "positive_2": {"class_type": "PromptValue", "inputs": {"text": "p2"}},
        "negative_2": {"class_type": "PromptValue", "inputs": {"text": "n2"}},
        "positive_1": {"class_type": "PromptValue", "inputs": {"text": "p1"}},
        "negative_1": {"class_type": "PromptValue", "inputs": {"text": "n1"}},
        "encode_positive_1": {
            "class_type": "UnknownEncoder",
            "inputs": {"text": ["positive_1", 0]},
        },
        "encode_negative_1": {
            "class_type": "UnknownEncoder",
            "inputs": {"text": ["negative_1", 0]},
        },
        "stage_1": {
            "class_type": "Stage",
            "inputs": {
                "positive": ["encode_positive_1", 0],
                "negative": ["encode_negative_1", 0],
            },
        },
        "bridge": {
            "class_type": "Bridge",
            "inputs": {"image": ["stage_1", 0]},
        },
        "encode_positive_2": {
            "class_type": "UnknownEncoder",
            "inputs": {"text": ["positive_2", 0]},
        },
        "encode_negative_2": {
            "class_type": "UnknownEncoder",
            "inputs": {"text": ["negative_2", 0]},
        },
        "stage_2": {
            "class_type": "Stage",
            "inputs": {
                "image": ["bridge", 0],
                "positive": ["encode_positive_2", 0],
                "negative": ["encode_negative_2", 0],
            },
        },
    }


def test_cube_snapshot_places_every_detected_prompt_before_ordinary_cards() -> None:
    """The shared snapshot should treat one cube as a prompt-first section."""

    cube = cube_state(nodes=_two_stage_nodes())

    snapshot = build_behavior_snapshot(
        cube_states={"Cube": cube},
        stack_order=["Cube"],
        definitions_by_class=_DEFINITIONS,
    )

    assert snapshot.card_order_by_alias["Cube"][:4] == (
        "positive_1",
        "negative_1",
        "positive_2",
        "negative_2",
    )


def test_direct_snapshot_opens_first_pair_and_keeps_second_pair_after_first_stage() -> (
    None
):
    """The production snapshot should keep a later workflow pair stage-local."""

    nodes = _two_stage_nodes()
    state = DirectWorkflowState(
        source_path=Path("two-stage.json"),
        source_workflow={},
        buffer={"nodes": nodes},
    )

    snapshot = build_behavior_snapshot(
        cube_states={"Direct": state},
        stack_order=["Direct"],
        definitions_by_class=_DEFINITIONS,
    )

    order = snapshot.card_order_by_alias["Direct"]
    assert order[:2] == ("positive_1", "negative_1")
    assert order.index("stage_1") < order.index("positive_2")
    assert order.index("negative_2") < order.index("bridge")
    assert snapshot.prompt_contexts_by_alias["Direct"][0].anchor_node_name == (
        "stage_1"
    )
    assert snapshot.prompt_contexts_by_alias["Direct"][1].anchor_node_name == (
        "stage_2"
    )
