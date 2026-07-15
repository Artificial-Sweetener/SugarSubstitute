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

"""Contract tests for prompts-first wired node-card ordering."""

from __future__ import annotations

from substitute.application.node_behavior.node_card_order import order_node_cards


def test_order_node_cards_keeps_prompt_nodes_first_by_legacy_name() -> None:
    """Prompt nodes should stay pinned before the wired graph body."""

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

    order = order_node_cards(nodes)

    assert order[:2] == ["positive_prompt", "negative_prompt"]
    assert set(order) == set(nodes)


def test_order_node_cards_keeps_simple_wired_chain_order() -> None:
    """Wired dependencies should order upstream nodes before consumers."""

    nodes: dict[str, object] = {
        "save": {"inputs": {"images": ["sampler", 0]}},
        "sampler": {"inputs": {"latent": ["encoder", 0]}},
        "loader": {"inputs": {}},
        "encoder": {"inputs": {"model": ["loader", 0]}},
    }

    assert order_node_cards(nodes) == ["loader", "encoder", "sampler", "save"]


def test_order_node_cards_preserves_mapping_order_for_independent_branches() -> None:
    """Independent zero-degree branches should retain source mapping order."""

    nodes: dict[str, object] = {
        "branch_b_source": {"inputs": {}},
        "branch_a_source": {"inputs": {}},
        "branch_b_output": {"inputs": {"value": ["branch_b_source", 0]}},
        "branch_a_output": {"inputs": {"value": ["branch_a_source", 0]}},
    }

    assert order_node_cards(nodes) == [
        "branch_b_source",
        "branch_a_source",
        "branch_b_output",
        "branch_a_output",
    ]


def test_order_node_cards_appends_cycles_in_mapping_order() -> None:
    """Cyclic leftovers should not crash and should keep deterministic order."""

    nodes: dict[str, object] = {
        "acyclic": {"inputs": {}},
        "cycle_a": {"inputs": {"value": ["cycle_b", 0]}},
        "cycle_b": {"inputs": {"value": ["cycle_a", 0]}},
    }

    assert order_node_cards(nodes) == ["acyclic", "cycle_a", "cycle_b"]


def test_order_node_cards_does_not_prioritize_model_or_sampler_names() -> None:
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

    assert order_node_cards(nodes) == ["checkpoint", "latent_source", "ksampler"]


def test_order_node_cards_uses_layout_title_for_prompt_roles() -> None:
    """Layout titles should identify prompt roles before legacy-name fallback."""

    nodes: dict[str, object] = {
        "sampler": {
            "inputs": {
                "positive": ["text_b", 0],
                "negative": ["text_a", 0],
            }
        },
        "text_a": {"inputs": {}},
        "text_b": {"inputs": {}},
    }
    layout_nodes: dict[str, object] = {
        "text_a": {"title": "Negative Prompt"},
        "text_b": {"title": "Positive Prompt"},
    }

    assert order_node_cards(nodes, layout_nodes=layout_nodes)[:2] == [
        "text_b",
        "text_a",
    ]
