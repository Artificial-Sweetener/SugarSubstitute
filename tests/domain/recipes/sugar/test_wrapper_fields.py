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

"""Sugar recipe wrapper-field contracts."""

from collections import OrderedDict


from substitute.domain.recipes.sugar_script_parser import (
    parse_sugar_script_document,
)
from tests.domain.recipes.sugar.serialization_support import serialize_sugar_script
from tests.domain.recipes.sugar.persistence_support import (
    _nested_mapping,
    _nested_value,
)


def test_sugar_script_addresses_subgraph_wrapper_surface_fields_only() -> None:
    """SugarScript should persist wrapper public fields without exposing body nodes."""

    stripped = OrderedDict(
        {
            "A": OrderedDict(
                cube_id="SDXL/Automask Detailer",
                nodes={
                    "detailer": {
                        "class_type": "644694cf-354b-4cc8-8a67-a78145a8180e",
                        "inputs": {"denoise": 0.6},
                    }
                },
                subgraphs=[
                    {
                        "id": "644694cf-354b-4cc8-8a67-a78145a8180e",
                        "nodes": [
                            {
                                "id": 1470,
                                "type": "DetailerForEach",
                                "inputs": [{"name": "denoise"}],
                            }
                        ],
                    }
                ],
            )
        }
    )

    script = serialize_sugar_script(stripped, ["A"], None)
    parsed = parse_sugar_script_document(script).buffers

    assert "set A.detailer.denoise = 0.6" in script
    assert "DetailerForEach.denoise" not in script
    assert "1470" not in script
    assert _nested_value(parsed["A"], "nodes", "detailer", "inputs", "denoise") == 0.6
    assert "DetailerForEach" not in _nested_mapping(parsed["A"], "nodes")
