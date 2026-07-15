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

"""Contract tests for node-name and class-name search filtering."""

from __future__ import annotations

from substitute.application.editor_search import EditorSearchMode, EditorSearchService
from tests.node_behavior_test_helpers import (
    build_behavior_snapshot,
    cube_state,
)


def test_node_search_filters_by_name_and_class() -> None:
    cubes = {
        "A": cube_state(
            nodes={
                "ksampler": {"class_type": "KSampler", "inputs": {}},
                "vae": {"class_type": "VAELoader", "inputs": {}},
            }
        ),
        "B": cube_state(
            nodes={"ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {}}}
        ),
    }

    by_vae = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A", "B"],
        node_search_text="vae",
    )
    assert by_vae.card_decisions_by_alias["A"]["vae"].visible is True
    assert by_vae.card_decisions_by_alias["A"]["ksampler"].visible is False
    assert by_vae.card_decisions_by_alias["B"]["ckpt"].visible is False

    by_sampler = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A", "B"],
        node_search_text="sampl",
    )
    assert by_sampler.card_decisions_by_alias["A"]["ksampler"].visible is True
    assert by_sampler.card_decisions_by_alias["A"]["vae"].visible is False
    assert by_sampler.card_decisions_by_alias["B"]["ckpt"].visible is False

    by_node = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A", "B"],
        node_search_text="ckpt",
    )
    assert by_node.card_decisions_by_alias["B"]["ckpt"].visible is True
    assert by_node.card_decisions_by_alias["A"]["ksampler"].visible is False
    assert by_node.card_decisions_by_alias["A"]["vae"].visible is False

    base = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A", "B"],
        node_search_text=" ",
    )
    assert base.card_decisions_by_alias["A"]["ksampler"].visible is True
    assert base.card_decisions_by_alias["A"]["vae"].visible is True
    assert base.card_decisions_by_alias["B"]["ckpt"].visible is True


def test_node_search_matches_field_keys_and_beautified_labels() -> None:
    """Node searches should keep cards visible when one field key or label matches."""

    cubes = {
        "A": cube_state(
            nodes={
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {
                        "sampler_name": "euler",
                        "cfg": 7.0,
                    },
                },
                "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "foo.vae"}},
            }
        )
    }

    base_snapshot = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A"],
    )
    search_service = EditorSearchService()
    by_field_key_result = search_service.build_result(
        base_snapshot,
        search_service.build_query(
            mode=EditorSearchMode.NODE,
            raw_text="sampler_name",
        ),
    )
    by_field_key = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A"],
        search_matching_nodes=by_field_key_result.matching_nodes,
    )
    assert by_field_key.card_decisions_by_alias["A"]["ksampler"].visible is True
    assert by_field_key.card_decisions_by_alias["A"]["vae"].visible is False

    by_beautified_label_result = search_service.build_result(
        base_snapshot,
        search_service.build_query(
            mode=EditorSearchMode.NODE,
            raw_text="sampler",
        ),
    )
    by_beautified_label = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A"],
        search_matching_nodes=by_beautified_label_result.matching_nodes,
    )
    assert by_beautified_label.card_decisions_by_alias["A"]["ksampler"].visible is True
    assert by_beautified_label.card_decisions_by_alias["A"]["vae"].visible is False


def test_node_search_keeps_authored_bypass_nodes_hidden_until_revealed() -> None:
    cubes = {
        "A": cube_state(
            nodes={
                "vae": {
                    "class_type": "VAELoader",
                    "inputs": {},
                    "enabled": False,
                    "mode": 4,
                }
            }
        ),
        "B": cube_state(
            nodes={
                "vae": {
                    "class_type": "VAELoader",
                    "inputs": {},
                    "enabled": False,
                    "mode": 4,
                }
            }
        ),
    }

    base = build_behavior_snapshot(cube_states=cubes, stack_order=["A", "B"])
    assert base.card_decisions_by_alias["A"]["vae"].visible is False
    assert base.card_decisions_by_alias["B"]["vae"].visible is False

    searched = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A", "B"],
        node_search_text="vae",
    )
    assert searched.card_decisions_by_alias["A"]["vae"].visible is False
    assert searched.card_decisions_by_alias["B"]["vae"].visible is False
