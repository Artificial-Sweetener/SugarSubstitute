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

"""Contract tests for shared sampler/scheduler field-pipeline helpers."""

from __future__ import annotations

from substitute.domain.links import (
    apply_choice_selection,
    build_sampler_choice_items,
    build_scheduler_choice_items,
    resolve_linked_choice_label,
)


def test_build_sampler_choice_items_prefixes_links_before_literals() -> None:
    """Sampler choice items should expose link labels before literal options."""

    node_data = {
        "sampler_links": [
            {"from_cube": "A", "from_node": "ksampler", "label": "link:A"}
        ]
    }

    choice_items = build_sampler_choice_items(node_data, ["euler", "heun"])

    assert choice_items == [
        ("link:A", {"from_cube": "A", "from_node": "ksampler"}),
        ("euler", "euler"),
        ("heun", "heun"),
    ]


def test_build_scheduler_choice_items_uses_default_label_when_missing() -> None:
    """Scheduler choice items should synthesize a deterministic label when absent."""

    node_data = {"scheduler_links": [{"from_cube": "A", "from_node": "scheduler"}]}

    choice_items = build_scheduler_choice_items(node_data, ["normal"])

    assert choice_items[0] == (
        "-> A scheduler",
        {"from_cube": "A", "from_node": "scheduler"},
    )
    assert choice_items[1] == ("normal", "normal")


def test_resolve_linked_choice_label_matches_by_link_identity() -> None:
    """Linked choice label resolution should use from-cube and from-node identity."""

    choice_items = [
        ("link:A", {"from_cube": "A", "from_node": "ksampler"}),
        ("euler", "euler"),
    ]

    label = resolve_linked_choice_label(
        choice_items,
        {"from_cube": "A", "from_node": "ksampler"},
    )

    assert label == "link:A"


def test_apply_choice_selection_switches_between_literal_and_link_modes() -> None:
    """Choice application should keep literal and linked selection state mutually exclusive."""

    node_data = {"inputs": {"sampler_name": "euler"}}

    apply_choice_selection(
        node_data,
        literal_key="sampler_name",
        link_key="sampler_link",
        selected_value={"from_cube": "A", "from_node": "ksampler"},
    )
    assert node_data == {
        "inputs": {},
        "sampler_link": {"from_cube": "A", "from_node": "ksampler"},
    }

    apply_choice_selection(
        node_data,
        literal_key="sampler_name",
        link_key="sampler_link",
        selected_value="heun",
    )
    assert node_data == {"inputs": {"sampler_name": "heun"}}
