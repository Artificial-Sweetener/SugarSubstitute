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

"""Verify legacy force-visible state through the behavior service."""

from __future__ import annotations

from substitute.application.node_behavior import NodeBehaviorRuntimeState
from tests.support.node_behavior import (
    behavior_payload,
    build_behavior_snapshot,
    cube_state,
)


def test_force_visible_non_loader_respects_buffer_enabled() -> None:
    """Surface a legacy-visible card without overwriting explicit disable."""

    cubes = {
        "A": cube_state(
            nodes={
                "patch": {
                    "class_type": "CustomPatch",
                    "enabled": False,
                    "inputs": {},
                }
            },
            ui={
                "node_behavior_runtime": NodeBehaviorRuntimeState(
                    node_instance_patch=behavior_payload(
                        {
                            "controls": {
                                "by_node_instance": {"A:patch": {"force_visible": True}}
                            }
                        }
                    )
                )
            },
        )
    }

    decision = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A"],
    ).card_decisions_by_alias["A"]["patch"]

    assert decision.visible is True
    assert decision.enabled is False
    assert decision.reason == "explicit:disabled"


def test_force_visible_checkpoint_sets_reveal_checked() -> None:
    """Keep legacy-visible checkpoint state visibly checked after restoration."""

    cubes = {
        "A": cube_state(
            nodes={
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "same.safetensors"},
                }
            }
        ),
        "B": cube_state(
            nodes={
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "same.safetensors"},
                }
            },
            ui={
                "node_behavior_runtime": NodeBehaviorRuntimeState(
                    node_instance_patch=behavior_payload(
                        {
                            "controls": {
                                "by_node_instance": {"B:ckpt": {"force_visible": True}}
                            }
                        }
                    )
                )
            },
        ),
    }

    decision = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A", "B"],
    ).card_decisions_by_alias["B"]["ckpt"]

    assert decision.visible is True
    assert decision.enabled is True
    assert decision.reason == "legacy:force-visible"
    assert decision.reveal_checked is True


def test_checkpoint_respects_explicit_disable() -> None:
    """Keep a checkpoint visible while honoring explicit disable state."""

    cubes = {
        "A": cube_state(
            nodes={
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "enabled": False,
                    "inputs": {"checkpoint": "modelA.safetensors"},
                }
            }
        )
    }

    decision = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A"],
    ).card_decisions_by_alias["A"]["ckpt"]

    assert decision.visible is True
    assert decision.enabled is False
    assert decision.reason == "explicit:disabled"
