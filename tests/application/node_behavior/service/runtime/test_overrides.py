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

"""Runtime behavior-override contracts."""

from __future__ import annotations


from substitute.application.node_behavior import (
    NodeBehaviorRuntimeState,
)
from tests.support.node_behavior import (
    DummyNodeDefinitionGateway,
    build_behavior_snapshot,
    cube_state,
)


def test_build_snapshot_reveal_entries_track_revealable_hidden_nodes() -> None:
    """Reveal menu entries should come from the same node display decisions."""

    cubes = {
        "A": cube_state(
            nodes={"vae": {"class_type": "VAELoader", "inputs": {}, "mode": 4}},
        ),
        "B": cube_state(
            nodes={"ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
        ),
        "C": cube_state(
            nodes={
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "later"},
                    "mode": 4,
                }
            },
        ),
    }

    snapshot = build_behavior_snapshot(cube_states=cubes, stack_order=["A", "B", "C"])

    assert [entry.node_name for entry in snapshot.reveal_entries_by_alias["A"]] == [
        "vae"
    ]
    assert snapshot.reveal_entries_by_alias["B"] == []
    assert [entry.node_name for entry in snapshot.reveal_entries_by_alias["C"]] == [
        "ckpt"
    ]
    assert snapshot.reveal_entries_by_alias["A"][0].checked is False
    assert snapshot.reveal_entries_by_alias["C"][0].checked is False


def test_runtime_state_is_created_and_reused_on_cube_state() -> None:
    """Runtime state helper should store one mutable runtime bucket on the cube state."""

    cube = cube_state()

    first = NodeBehaviorRuntimeState()
    cube.ui["node_behavior_runtime"] = first

    from substitute.application.node_behavior import NodeBehaviorService

    service = NodeBehaviorService(node_definition_gateway=DummyNodeDefinitionGateway())
    second = service.ensure_runtime_state(cube)

    assert second is first


def test_set_node_activation_override_writes_explicit_override_and_dirty_flag() -> None:
    """Activation commands should persist only explicit user intent."""

    from substitute.application.node_behavior import NodeBehaviorService

    cube = cube_state(
        nodes={"vae": {"class_type": "VAELoader", "inputs": {}}},
    )
    service = NodeBehaviorService(node_definition_gateway=DummyNodeDefinitionGateway())

    service.set_node_activation_override(cube, "vae", True)
    assert cube.buffer["nodes"]["vae"]["enabled"] is True
    assert cube.dirty is True

    cube.dirty = False
    service.set_node_activation_override(cube, "vae", None)
    assert "enabled" not in cube.buffer["nodes"]["vae"]
    assert cube.dirty is True


def test_set_node_visibility_override_writes_reveal_state_and_dirty_flag() -> None:
    """Reveal commands should persist editor visibility separately from activation."""

    from substitute.application.node_behavior import NodeBehaviorService

    cube = cube_state(
        nodes={"vae": {"class_type": "VAELoader", "inputs": {}}},
    )
    service = NodeBehaviorService(node_definition_gateway=DummyNodeDefinitionGateway())

    service.set_node_visibility_override(cube, "vae", True)
    assert cube.buffer["nodes"]["vae"]["revealed"] is True
    assert cube.dirty is True

    cube.dirty = False
    service.set_node_visibility_override(cube, "vae", True)
    assert cube.dirty is False

    service.set_node_visibility_override(cube, "vae", None)
    assert "revealed" not in cube.buffer["nodes"]["vae"]
    assert cube.dirty is True


def test_activation_and_reveal_overrides_can_coexist_independently() -> None:
    """Disabled-but-revealed bypass-authored nodes should be representable."""

    cube = cube_state(
        nodes={
            "vae": {
                "class_type": "VAELoader",
                "inputs": {},
                "mode": 4,
                "enabled": False,
                "revealed": True,
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )
    decision = snapshot.card_decisions_by_alias["A"]["vae"]

    assert decision.visible is True
    assert decision.enabled is False
    assert decision.explicit_override is False
    assert decision.explicit_revealed is True
