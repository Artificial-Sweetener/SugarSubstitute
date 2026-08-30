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

"""Verify combined node-search visibility and hidden-field projection."""

from __future__ import annotations

from tests.support.node_behavior import build_behavior_snapshot, cube_state


def test_search_visibility_preserves_hidden_field_projection() -> None:
    """Apply node search and field hiding through one behavior snapshot."""

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
