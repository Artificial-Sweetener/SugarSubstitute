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

"""Additional contract tests for node-behavior defaults and runtime decisions."""

from __future__ import annotations

from substitute.application.node_behavior import (
    NodeBehaviorContext,
    NodeBehaviorRuntimeState,
    resolve_node_behavior,
)
from tests.node_behavior_test_helpers import (
    behavior_payload,
    build_behavior_snapshot,
    cube_state,
)


def test_field_style_for_falls_back_to_class_rule_field_tail() -> None:
    """Host defaults should apply class-level field styles without external overrides."""

    resolved = resolve_node_behavior(
        node_name="Node",
        class_type="VectorscopeCC",
        input_keys=("r",),
        context=NodeBehaviorContext(
            stack_order=("A",),
            cube_alias="A",
            node_name="Node",
            class_type="VectorscopeCC",
            node_title=None,
            live_node_definition=None,
            declarative_patch=None,
            hook_patch=None,
            workflow_overrides={},
            node_instance_patch=None,
        ),
    )
    field = resolved.fields["r"]
    assert field.control_name == "color_slider"
    assert field.label_override == "Red"


def test_visibility_for_node_non_loader_force_visible_respects_buffer_enabled() -> None:
    """Legacy force-visible should surface the card without overwriting explicit disable."""

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

    snapshot = build_behavior_snapshot(cube_states=cubes, stack_order=["A"])
    decision = snapshot.card_decisions_by_alias["A"]["patch"]

    assert decision.visible is True
    assert decision.enabled is False
    assert decision.reason == "explicit:disabled"


def test_visibility_for_node_checkpoint_force_visible_sets_reveal_checked() -> None:
    """Legacy force-visible should keep restored reveal state checked."""

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

    snapshot = build_behavior_snapshot(cube_states=cubes, stack_order=["A", "B"])
    decision = snapshot.card_decisions_by_alias["B"]["ckpt"]

    assert decision.visible is True
    assert decision.enabled is True
    assert decision.reason == "legacy:force-visible"
    assert decision.reveal_checked is True


def test_visibility_for_node_checkpoint_respects_explicit_disable() -> None:
    """Checkpoint loaders should stay visible while honoring explicit disable."""

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

    snapshot = build_behavior_snapshot(cube_states=cubes, stack_order=["A"])
    decision = snapshot.card_decisions_by_alias["A"]["ckpt"]

    assert decision.visible is True
    assert decision.enabled is False
    assert decision.reason == "explicit:disabled"
