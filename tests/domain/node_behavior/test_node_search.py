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

"""Verify node-name and class-name visibility filtering."""

from __future__ import annotations

from tests.support.node_behavior import build_behavior_snapshot, cube_state


def test_search_filters_by_node_name_and_class() -> None:
    """Match normalized node names and classes while hiding other cards."""

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

    unfiltered = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A", "B"],
        node_search_text=" ",
    )
    assert unfiltered.card_decisions_by_alias["A"]["ksampler"].visible is True
    assert unfiltered.card_decisions_by_alias["A"]["vae"].visible is True
    assert unfiltered.card_decisions_by_alias["B"]["ckpt"].visible is True


def test_search_does_not_reveal_authored_bypass_nodes() -> None:
    """Keep explicitly bypassed nodes hidden even when their names match."""

    cubes = {
        alias: cube_state(
            nodes={
                "vae": {
                    "class_type": "VAELoader",
                    "inputs": {},
                    "enabled": False,
                    "mode": 4,
                }
            }
        )
        for alias in ("A", "B")
    }

    unfiltered = build_behavior_snapshot(cube_states=cubes, stack_order=["A", "B"])
    assert unfiltered.card_decisions_by_alias["A"]["vae"].visible is False
    assert unfiltered.card_decisions_by_alias["B"]["vae"].visible is False

    searched = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A", "B"],
        node_search_text="vae",
    )
    assert searched.card_decisions_by_alias["A"]["vae"].visible is False
    assert searched.card_decisions_by_alias["B"]["vae"].visible is False
