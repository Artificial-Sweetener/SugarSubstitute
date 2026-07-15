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

"""Tests for editor field factory immutable combo preparation cache."""

from __future__ import annotations

import substitute.presentation.editor.panel.factories.choice_factory as choice_factory


def test_prepared_combo_items_reuses_immutable_literal_items() -> None:
    """Repeated literal combo preparation should return the same values."""

    choice_factory._clear_combo_item_cache_for_tests()

    first = choice_factory._prepared_combo_items(
        key="ckpt_name",
        node_data={},
        options=("a.safetensors", "b.safetensors"),
    )
    second = choice_factory._prepared_combo_items(
        key="ckpt_name",
        node_data={},
        options=("a.safetensors", "b.safetensors"),
    )

    assert first == second
    assert first == [
        ("a.safetensors", "a.safetensors"),
        ("b.safetensors", "b.safetensors"),
    ]


def test_prepared_combo_items_returns_independent_link_values() -> None:
    """Linked combo preparation should not share mutable backend dicts."""

    choice_factory._clear_combo_item_cache_for_tests()
    node_data = {
        "sampler_links": [
            {
                "label": "Linked sampler",
                "from_cube": "Source",
                "from_node": "sampler",
            }
        ]
    }

    first = choice_factory._prepared_combo_items(
        key="sampler_name",
        node_data=node_data,
        options=("euler",),
    )
    second = choice_factory._prepared_combo_items(
        key="sampler_name",
        node_data=node_data,
        options=("euler",),
    )

    assert first == second
    assert isinstance(first[0][1], dict)
    assert isinstance(second[0][1], dict)
    assert first[0][1] is not second[0][1]
