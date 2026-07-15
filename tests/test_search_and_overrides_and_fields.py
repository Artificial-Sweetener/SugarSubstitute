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

"""Contract tests for search filtering plus hidden-field merging."""

from __future__ import annotations

from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state


def test_overrides_and_node_search_and_field_search_and_semantics():
    cubes = {
        "A": cube_state(
            nodes={
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {"seed": 0, "steps": 20},
                },
                "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            },
        )
    }

    snapshot = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A"],
        node_search_text="checkpoint",
        workflow_overrides={},
        search_hidden_keys={"seed"},
    )

    assert snapshot.card_decisions_by_alias["A"]["ksampler"].visible is False
    assert "seed" in snapshot.hidden_field_keys_by_alias["A"]
