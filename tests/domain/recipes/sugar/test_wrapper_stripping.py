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

"""Verify recipe stripping preserves only a subgraph wrapper's public surface."""

from __future__ import annotations

from collections import OrderedDict
from typing import cast

from substitute.application.recipes.sugar_label_resolution import SugarScriptLabelIndex
from substitute.domain.recipes.recipe_buffers import strip_recipe_buffers
from substitute.domain.workflow import CubeState
from tests.domain.recipes.sugar.serialization_support import serialize_sugar_script


UUID_WRAPPER = "94f725d5-39bf-4060-be68-f573214a2055"


def _wrapper_cube_payload() -> dict[str, object]:
    """Build a cube whose public wrapper encloses one internal dual-output node."""

    implementation = {
        "nodes": {
            "source": {"class_type": "SourceNode", "inputs": {"value": 1}},
            "wrapper": {
                "class_type": UUID_WRAPPER,
                "inputs": {
                    "x": ["source", 0],
                    "y": 3,
                },
            },
            "consumer": {
                "class_type": "ConsumerNode",
                "inputs": {
                    "main": ["wrapper", 0],
                    "aux": ["wrapper", 1],
                },
            },
        },
        "inputs": {},
        "outputs": {"output.main": "consumer"},
        "layout": {},
        "definitions": {},
        "subgraphs": [
            {
                "id": UUID_WRAPPER,
                "inputNode": {"id": -10},
                "outputNode": {"id": -20},
                "inputs": [
                    {"name": "x", "label": "X", "linkIds": [11]},
                    {"name": "y", "label": "Y", "linkIds": [12]},
                ],
                "outputs": [
                    {"name": "main", "label": "Main", "linkIds": [13]},
                    {"name": "aux", "label": "Aux", "linkIds": [14]},
                ],
                "links": [
                    [11, -10, 0, 1, "in_a", "ANY"],
                    [12, -10, 1, 1, "in_b", "ANY"],
                    [13, 1, 0, -20, 0, "ANY"],
                    [14, 1, 1, -20, 1, "ANY"],
                ],
                "nodes": [
                    {
                        "id": 1,
                        "type": "DualOut",
                        "inputs": [
                            {"name": "in_a", "link": 11},
                            {"name": "in_b", "link": 12},
                        ],
                    }
                ],
            }
        ],
    }
    return {
        "cube_id": "wrapper_cube",
        "version": "1.0.0",
        "implementation": implementation,
        "surface": {"default_flavor_id": "default", "controls": []},
        "flavors": {"authored": [{"id": "default", "name": "Default", "values": {}}]},
    }


def test_script_generation_stays_wrapper_surface_only() -> None:
    """Strip internal subgraph body nodes before SugarScript serialization."""

    cube = _wrapper_cube_payload()
    implementation = cast(dict[str, object], cube["implementation"])
    cube_id = cast(str, cube["cube_id"])
    version = cast(str, cube["version"])
    nodes = cast(dict[str, object], implementation["nodes"])
    subgraphs = cast(list[object], implementation["subgraphs"])
    cube_buffer: OrderedDict[str, object] = OrderedDict(
        (
            ("cube_id", cube_id),
            ("version", version),
            ("nodes", OrderedDict(nodes)),
            ("subgraphs", subgraphs),
            (
                "definitions",
                {
                    "DualOut": {
                        "input": {"required": {"in_a": ["INT"], "in_b": ["INT"]}}
                    }
                },
            ),
        )
    )
    state = CubeState(
        cube_id=cube_id,
        version=version,
        alias="A",
        original_cube=cube,
        buffer=cube_buffer,
    )

    stripped = strip_recipe_buffers(["A"], {"A": state})
    script = serialize_sugar_script(
        stripped,
        ["A"],
        global_overrides=None,
        label_resolver=SugarScriptLabelIndex.from_cube_graphs({"A": stripped["A"]}),
    )

    assert "set A.wrapper.Y = 3" in script
    assert "DualOut" not in script
    assert UUID_WRAPPER not in script
