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

"""Verify editor-search results integrate with node visibility policy."""

from __future__ import annotations

from substitute.application.editor_search import EditorSearchMode, EditorSearchService
from tests.support.node_behavior import build_behavior_snapshot, cube_state


def test_node_mode_matches_field_keys_and_beautified_labels() -> None:
    """Keep a node visible when node-mode search matches one owned field."""

    cubes = {
        "A": cube_state(
            nodes={
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {"sampler_name": "euler", "cfg": 7.0},
                },
                "vae": {
                    "class_type": "VAELoader",
                    "inputs": {"vae_name": "foo.vae"},
                },
            }
        )
    }
    base_snapshot = build_behavior_snapshot(cube_states=cubes, stack_order=["A"])
    service = EditorSearchService()

    by_key_result = service.build_result(
        base_snapshot,
        service.build_query(
            mode=EditorSearchMode.NODE,
            raw_text="sampler_name",
        ),
    )
    by_key = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A"],
        search_matching_nodes=by_key_result.matching_nodes,
    )
    assert by_key.card_decisions_by_alias["A"]["ksampler"].visible is True
    assert by_key.card_decisions_by_alias["A"]["vae"].visible is False

    by_label_result = service.build_result(
        base_snapshot,
        service.build_query(mode=EditorSearchMode.NODE, raw_text="sampler"),
    )
    by_label = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A"],
        search_matching_nodes=by_label_result.matching_nodes,
    )
    assert by_label.card_decisions_by_alias["A"]["ksampler"].visible is True
    assert by_label.card_decisions_by_alias["A"]["vae"].visible is False
