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

"""Behavior snapshot card-order contracts."""

from __future__ import annotations


from tests.support.node_behavior import (
    build_behavior_snapshot,
    cube_state,
)


def test_behavior_snapshot_separates_baseline_resolution_from_final_card_order() -> (
    None
):
    """Keep metadata maps wired while exposing prompt priority in the card plan."""

    cube = cube_state(
        nodes={
            "ksampler": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["checkpoint", 0],
                    "positive": ["text_b", 0],
                    "negative": ["text_a", 0],
                    "latent": ["latent_source", 0],
                },
            },
            "latent_source": {
                "class_type": "CustomLatentProducer",
                "inputs": {"model": ["checkpoint", 0]},
            },
            "checkpoint": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            },
            "text_a": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "low quality"},
            },
            "text_b": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "portrait"},
            },
        },
    )
    cube.buffer["layout"] = {
        "nodes": {
            "text_a": {"title": "Negative Prompt"},
            "text_b": {"title": "Positive Prompt"},
        }
    }

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "CLIPTextEncode": {
                "input": {
                    "required": {"text": ["STRING", {"multiline": True}]},
                },
                "output": ["CONDITIONING"],
            },
            "KSampler": {
                "input": {
                    "required": {
                        "positive": ["CONDITIONING", {}],
                        "negative": ["CONDITIONING", {}],
                    }
                }
            },
        },
    )

    assert list(snapshot.resolved_nodes_by_alias["A"]) == [
        "checkpoint",
        "text_a",
        "text_b",
        "latent_source",
        "ksampler",
    ]
    assert snapshot.card_order_by_alias["A"] == (
        "text_b",
        "text_a",
        "checkpoint",
        "latent_source",
        "ksampler",
    )
