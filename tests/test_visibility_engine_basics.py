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

"""Contract tests for the unified node-behavior snapshot engine."""

from __future__ import annotations

from substitute.application.node_behavior import NodeBehaviorRuntimeState
from tests.node_behavior_test_helpers import (
    behavior_payload,
    build_behavior_snapshot,
    cube_state,
)


def test_engine_card_and_fields_decisions_basic() -> None:
    """Snapshot should merge authored bypass decisions with hidden-field state."""

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
