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

"""Contract tests for stable graph order and reachability."""

from __future__ import annotations

from substitute.application.node_behavior.node_card_order import (
    downstream_node_graph,
    node_reaches,
    wired_node_order,
)


def test_wired_order_does_not_assign_prompt_priority_before_resolution() -> None:
    """Baseline metadata order should remain independent of presentation semantics."""

    nodes: dict[str, object] = {
        "ksampler": {
            "inputs": {
                "positive": ["positive_prompt", 0],
                "negative": ["negative_prompt", 0],
            }
        },
        "upstream": {"inputs": {}},
        "negative_prompt": {"inputs": {}},
        "positive_prompt": {"inputs": {}},
    }

    order = wired_node_order(nodes)

    assert order == ["upstream", "negative_prompt", "positive_prompt", "ksampler"]
    assert set(order) == set(nodes)


def test_wired_node_order_keeps_simple_wired_chain_order() -> None:
    """Wired dependencies should order upstream nodes before consumers."""

    nodes: dict[str, object] = {
        "save": {"inputs": {"images": ["sampler", 0]}},
        "sampler": {"inputs": {"latent": ["encoder", 0]}},
        "loader": {"inputs": {}},
        "encoder": {"inputs": {"model": ["loader", 0]}},
    }

    assert wired_node_order(nodes) == ["loader", "encoder", "sampler", "save"]


def test_wired_node_order_preserves_mapping_order_for_independent_branches() -> None:
    """Independent zero-degree branches should retain source mapping order."""

    nodes: dict[str, object] = {
        "branch_b_source": {"inputs": {}},
        "branch_a_source": {"inputs": {}},
        "branch_b_output": {"inputs": {"value": ["branch_b_source", 0]}},
        "branch_a_output": {"inputs": {"value": ["branch_a_source", 0]}},
    }

    assert wired_node_order(nodes) == [
        "branch_b_source",
        "branch_a_source",
        "branch_b_output",
        "branch_a_output",
    ]


def test_wired_node_order_appends_cycles_in_mapping_order() -> None:
    """Cyclic leftovers should not crash and should keep deterministic order."""

    nodes: dict[str, object] = {
        "acyclic": {"inputs": {}},
        "cycle_a": {"inputs": {"value": ["cycle_b", 0]}},
        "cycle_b": {"inputs": {"value": ["cycle_a", 0]}},
    }

    assert wired_node_order(nodes) == ["acyclic", "cycle_a", "cycle_b"]


def test_wired_node_order_does_not_prioritize_model_or_sampler_names() -> None:
    """Model and sampler class names should not jump ahead of wired inputs."""

    nodes: dict[str, object] = {
        "ksampler": {
            "class_type": "KSampler",
            "inputs": {"latent": ["latent_source", 0]},
        },
        "checkpoint": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "model.safetensors"},
        },
        "latent_source": {
            "class_type": "CustomLatentProducer",
            "inputs": {"model": ["checkpoint", 0]},
        },
    }

    assert wired_node_order(nodes) == ["checkpoint", "latent_source", "ksampler"]


def test_node_reachability_is_cycle_safe_and_directional() -> None:
    """Segment planning should query local topology without recursion hazards."""

    graph = downstream_node_graph(
        {
            "source": {"inputs": {}},
            "cycle_a": {"inputs": {"value": ["source", 0], "loop": ["cycle_b", 0]}},
            "cycle_b": {"inputs": {"value": ["cycle_a", 0]}},
            "sink": {"inputs": {"value": ["cycle_b", 0]}},
        }
    )

    assert node_reaches(graph, "source", "sink")
    assert node_reaches(graph, "cycle_b", "cycle_a")
    assert not node_reaches(graph, "sink", "source")
