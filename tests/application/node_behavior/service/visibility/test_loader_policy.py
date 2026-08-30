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

"""Verify loader visibility follows authored policy and explicit runtime state."""

from __future__ import annotations

from substitute.application.node_behavior import NodeBehaviorRuntimeState
from tests.support.node_behavior import (
    behavior_payload,
    build_behavior_snapshot,
    cube_state,
)


def test_loader_visibility_combines_authored_bypass_and_runtime_reveal() -> None:
    """Merge authored bypass, explicit reveal, and hidden override fields."""

    cubes = {
        "A": cube_state(
            nodes={
                "vae": {"class_type": "VAELoader", "inputs": {}, "mode": 4},
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {"sampler_name": "euler", "scheduler": "karras"},
                },
            },
        ),
        "B": cube_state(
            nodes={
                "vae": {"class_type": "VAELoader", "inputs": {}, "mode": 4},
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {"sampler_name": "heun", "scheduler": "normal"},
                },
            },
            ui={
                "node_behavior_runtime": NodeBehaviorRuntimeState(
                    node_instance_patch=behavior_payload(
                        {
                            "controls": {
                                "by_node_instance": {"B:vae": {"force_visible": True}}
                            }
                        }
                    )
                )
            },
        ),
    }

    snapshot = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A", "B"],
        workflow_overrides={
            "sampler_name": {"value": "Euler"},
            "scheduler": {"value": "karras"},
        },
    )

    assert snapshot.card_decisions_by_alias["A"]["vae"].visible is False
    assert snapshot.card_decisions_by_alias["A"]["vae"].enabled is False
    assert snapshot.card_decisions_by_alias["B"]["vae"].visible is True
    assert snapshot.card_decisions_by_alias["B"]["vae"].enabled is True
    assert ("A", "ksampler", "sampler_name") in snapshot.hidden_field_keys_by_alias["A"]
    assert ("B", "ksampler", "scheduler") in snapshot.hidden_field_keys_by_alias["B"]


def test_checkpoint_visibility_is_independent_of_cube_stack_order() -> None:
    """Keep authored checkpoint loaders visible after cube reordering."""

    cubes = {
        "A": cube_state(
            nodes={
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "a.safetensors"},
                }
            }
        ),
        "B": cube_state(
            nodes={
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "b.safetensors"},
                }
            }
        ),
    }

    snapshot_ab = build_behavior_snapshot(cube_states=cubes, stack_order=["A", "B"])
    snapshot_ba = build_behavior_snapshot(cube_states=cubes, stack_order=["B", "A"])

    for alias in ("A", "B"):
        assert snapshot_ab.card_decisions_by_alias[alias]["ckpt"].visible is True
        assert snapshot_ab.card_decisions_by_alias[alias]["ckpt"].enabled is True
        assert snapshot_ba.card_decisions_by_alias[alias]["ckpt"].visible is True
        assert snapshot_ba.card_decisions_by_alias[alias]["ckpt"].enabled is True
