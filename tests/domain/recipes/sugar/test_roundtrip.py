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

"""Sugar recipe persistence round-trip contracts."""

from collections import OrderedDict


from substitute.domain.common import JsonObject
from substitute.domain.recipes.recipe_buffers import (
    merge_recipe_buffer,
    strip_recipe_buffers,
)
from substitute.domain.recipes.sugar_script_parser import (
    parse_sugar_script_document,
)
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.workflow import CubeState
from tests.domain.recipes.sugar.serialization_support import serialize_sugar_script
from tests.domain.recipes.sugar.persistence_support import (
    _RecipeCubeStub,
    _nested_mapping,
    _nested_value,
)


def test_buffers_to_and_from_sugar_script_roundtrip() -> None:
    """Core recipe buffers should survive serialization and parsing."""

    ordered_aliases = ["A", "B"]
    buffers = {
        "A": OrderedDict(
            cube_id="Text To Image",
            nodes={
                "positive_prompt": {
                    "inputs": {
                        "prompt_template": "a cat",
                        "steps": 20,
                    }
                },
                "sampler": {
                    "inputs": {
                        "sampler_name": "euler",
                    }
                },
            },
        ),
        "B": OrderedDict(cube_id="Image Saver", nodes={}),
    }

    stripped = strip_recipe_buffers(
        ordered_aliases,
        {
            alias: _RecipeCubeStub(
                cube_id=str(buffers[alias]["cube_id"]),
                version="1.0.0",
                buffer=buffers[alias],
            )
            for alias in ordered_aliases
        },
    )
    script = serialize_sugar_script(
        stripped,
        ordered_aliases,
        global_overrides={"seed": {"value": 1234, "mode": "global"}},
    )
    assert 'use "Text To Image"@1.0.0 as A' in script
    assert 'use "Image Saver"@1.0.0 as B' in script
    assert "set *.*.seed = 1234" in script
    assert 'set A.positive_prompt.prompt_template = "a cat"' in script

    parsed_document = parse_sugar_script_document(script)
    assert parsed_document.project_name is None
    assert parsed_document.global_overrides["seed"]["value"] == 1234
    assert parsed_document.buffers["A"]["cube_id"] == "Text To Image"
    assert parsed_document.buffers["A"]["version"] == "1.0.0"
    assert (
        _nested_value(
            parsed_document.buffers["A"],
            "nodes",
            "positive_prompt",
            "inputs",
            "prompt_template",
        )
        == "a cat"
    )


def test_seed_control_metadata_round_trips_fixed_modes_only() -> None:
    """SugarScript metadata should preserve non-default seed lock modes."""

    ordered_aliases = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="Text To Image",
            nodes={
                "ksampler": {
                    "inputs": {
                        "seed": 1234,
                        "steps": 20,
                    }
                },
            },
        )
    }

    script = serialize_sugar_script(
        stripped,
        ordered_aliases,
        field_control_states_by_alias={
            "A": {
                "ksampler": {
                    "seed": SeedControlState(SeedMode.FIXED),
                    "steps": SeedControlState(SeedMode.RANDOM),
                }
            }
        },
        override_control_states={
            "seed": SeedControlState(SeedMode.FIXED),
            "steps": SeedControlState(SeedMode.RANDOM),
        },
    )

    assert (
        '# seed_control {"alias":"A","field":"seed","mode":"fixed","node":"ksampler"}'
        in script
    )
    assert '# global_override_seed_control {"key":"seed","mode":"fixed"}' in script
    assert '"field":"steps"' not in script
    parsed = parse_sugar_script_document(script)
    assert (
        parsed.field_control_states_by_alias["A"]["ksampler"]["seed"].mode
        == SeedMode.FIXED
    )
    assert parsed.override_control_states["seed"].mode == SeedMode.FIXED


def test_strip_recipe_buffers_omits_definitions_and_preserves_cube_identity() -> None:
    """Persistence buffers should omit runtime definitions and retain identity."""

    ordered = ["A"]
    original_buffer: JsonObject = OrderedDict(
        cube_id="X", definitions={"foo": 1}, nodes={}
    )
    cs = CubeState(
        cube_id="X",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer=original_buffer,
    )
    stripped = strip_recipe_buffers(ordered, {"A": cs})
    assert "definitions" not in stripped["A"]
    assert stripped["A"]["cube_id"] == "X"


def test_recipe_serialization_omits_cube_source_metadata_comments() -> None:
    """Recipe text should not persist cube source diagnostics."""

    ordered = ["A"]
    cube = CubeState(
        cube_id="Artificial-Sweetener/Base-Cubes/demo.cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer=OrderedDict(
            cube_id="Artificial-Sweetener/Base-Cubes/demo.cube",
            version="1.0.0",
            nodes={},
        ),
        display_name="Demo",
        ui={
            "source": {
                "kind": "github",
                "repo_ref": "Artificial-Sweetener/Base-Cubes",
                "path": "demo.cube",
                "local_head_sha": "abc123",
                "dirty": True,
            },
        },
    )

    stripped = strip_recipe_buffers(ordered, {"A": cube})
    script = serialize_sugar_script(stripped, ordered)
    parsed = parse_sugar_script_document(script)

    assert 'use "Artificial-Sweetener/Base-Cubes/demo.cube"@1.0.0 as A' in script
    assert "cube_metadata" not in script
    assert "local_head_sha" not in script
    assert "repo_ref" not in script
    assert "source_path" not in script
    assert "dirty" not in script
    assert "content_hash" not in script
    assert "cube_metadata" not in parsed.buffers["A"]


def test_merge_recipe_buffer_schema_limited_and_meta_allowed() -> None:
    """Buffer patches should respect schema fields while retaining link metadata."""

    buffer: JsonObject = {
        "nodes": {
            "a": {
                "inputs": {
                    "x": 1,
                }
            }
        }
    }
    patch: JsonObject = {
        "foo": 1,  # not in schema
        "nodes": {
            "a": {
                "inputs": {"x": 2},
                "unknown": "z",  # not in schema
            }
        },
        "prompt_link": {"from_cube": "B"},  # meta allowed
    }
    schema: JsonObject = {
        "nodes": {
            "a": {
                "inputs": {"x": 0},
            }
        }
    }
    merge_recipe_buffer(buffer, patch, cube_definition=schema)
    # x updated, unknown and foo rejected, meta kept
    assert _nested_value(buffer, "nodes", "a", "inputs", "x") == 2
    assert "unknown" not in _nested_mapping(buffer, "nodes", "a")
    assert "foo" not in buffer
    assert buffer["prompt_link"] == {"from_cube": "B"}


def test_serialize_sugar_script_parse_roundtrip_is_idempotent_for_core_persistence() -> (
    None
):
    """Serialize->parse->serialize should preserve behavior-critical script structure."""
    ordered_aliases = ["A", "Alias With Space"]
    stripped_buffers = {
        "A": OrderedDict(
            cube_id="Text To Image",
            nodes={
                "positive_prompt": {
                    "inputs": {"prompt_template": "line1\nline2"},
                    "node_link": {
                        "from_cube": "Alias With Space",
                        "from_node": "positive_prompt",
                    },
                },
                "ksampler": {
                    "inputs": {"sampler_name": "euler", "scheduler": "normal"},
                },
            },
        ),
        "Alias With Space": OrderedDict(
            cube_id="Upscale",
            nodes={
                "disabled node": {"enabled": False, "inputs": {}},
            },
        ),
    }
    global_overrides = {"seed": {"value": 1234, "mode": "global"}}
    global_override_selections = {"seed": True, "scheduler": False}

    first_script = serialize_sugar_script(
        stripped_buffers,
        ordered_aliases,
        global_overrides,
        global_override_selections=global_override_selections,
    )
    parsed_document = parse_sugar_script_document(first_script)
    parsed_buffers = parsed_document.buffers
    parsed_overrides = parsed_document.global_overrides
    parsed_selections = parsed_document.global_override_selections
    second_script = serialize_sugar_script(
        parsed_buffers,
        list(parsed_buffers.keys()),
        parsed_overrides,
        global_override_selections=parsed_selections,
    )

    assert second_script == first_script
