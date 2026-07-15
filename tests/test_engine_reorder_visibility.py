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

"""Contract tests for reorder-independent loader visibility decisions."""

from __future__ import annotations

from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state


def test_checkpoint_visibility_does_not_change_on_reorder_engine_level() -> None:
    """Checkpoint visibility should follow authored bypass metadata, not stack order."""

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
    assert snapshot_ab.card_decisions_by_alias["A"]["ckpt"].visible is True
    assert snapshot_ab.card_decisions_by_alias["A"]["ckpt"].enabled is True
    assert snapshot_ab.card_decisions_by_alias["B"]["ckpt"].visible is True
    assert snapshot_ab.card_decisions_by_alias["B"]["ckpt"].enabled is True

    snapshot_ba = build_behavior_snapshot(cube_states=cubes, stack_order=["B", "A"])
    assert snapshot_ba.card_decisions_by_alias["B"]["ckpt"].visible is True
    assert snapshot_ba.card_decisions_by_alias["B"]["ckpt"].enabled is True
    assert snapshot_ba.card_decisions_by_alias["A"]["ckpt"].visible is True
    assert snapshot_ba.card_decisions_by_alias["A"]["ckpt"].enabled is True
