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

"""Protect projection of canonical authored cube inputs into recipe values."""

from __future__ import annotations

from substitute.application.recipes.authored_input_projection import (
    RecipeAuthoredInputProjector,
)


def test_authored_input_projection_preserves_lists_without_structural_values() -> None:
    """Projection should preserve authored lists and exclude external bindings."""

    graph = {
        "nodes": {
            "node": {
                "inputs": {
                    "image": ["@binding", "input.image"],
                    "strength": 0.5,
                    "masks": ["first.png", "second.png"],
                }
            }
        },
        "inputs": {"input.image": {"targets": [["node", "image"]]}},
        "surface": {
            "controls": [
                {
                    "control_id": "node.strength",
                    "symbol": "node",
                    "input_name": "strength",
                    "label": "strength",
                    "class_type": "TestNode",
                    "value_type": "object",
                },
                {
                    "control_id": "node.masks",
                    "symbol": "node",
                    "input_name": "masks",
                    "label": "masks",
                    "class_type": "TestNode",
                    "value_type": "object",
                },
            ]
        },
    }

    projected = RecipeAuthoredInputProjector().project(
        buffers={"A": graph},
        ordered_aliases=("A",),
    )

    assert [
        (assignment.node_key, assignment.input_key, assignment.value)
        for assignment in projected["A"]
    ] == [
        ("node", "strength", 0.5),
        ("node", "masks", ["first.png", "second.png"]),
    ]
