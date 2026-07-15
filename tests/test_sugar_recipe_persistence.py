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

"""Characterize Sugar recipe serialization, parsing, and persistence round trips."""

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from substitute.domain.common import JsonObject
from substitute.domain.recipes.recipe_buffers import (
    merge_recipe_buffer,
    restore_recipe_cube_state,
    strip_recipe_buffers,
)
from substitute.domain.recipes.sugar_links import (
    node_reference,
    prompt_field_reference,
    prompt_link_source_alias,
)
from substitute.domain.recipes.sugar_script_parser import (
    parse_sugar_script_document,
)
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from substitute.domain.cube_library import CubeUpdatePolicy
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.workflow import CubeState
from tests.sugar_serialization_test_helpers import serialize_sugar_script


@dataclass(frozen=True)
class _RecipeCubeStub:
    """Provide typed cube state for recipe buffer tests."""

    cube_id: str
    version: str
    buffer: Mapping[str, object]


def _nested_value(mapping: Mapping[str, object], *keys: str) -> object:
    """Return a value from nested JSON mappings with runtime narrowing."""

    current: object = mapping
    for key in keys:
        assert isinstance(current, Mapping)
        current = current[key]
    return current


def _nested_mapping(
    mapping: Mapping[str, object],
    *keys: str,
) -> Mapping[str, object]:
    """Return a nested JSON mapping with runtime narrowing."""

    value = _nested_value(mapping, *keys)
    assert isinstance(value, Mapping)
    return value


def test_prompt_link_reference_and_parse() -> None:
    """Prompt and node link references should quote and parse aliases."""

    ref = prompt_field_reference("My Cube", "positive_prompt", "prompt_template")
    assert ref == '"My Cube".positive_prompt.prompt_template'

    # Must parse only for positive/negative_prompt nodes and prompt_template param
    alias = prompt_link_source_alias("positive_prompt", "prompt_template", ref)
    assert alias == "My Cube"
    assert prompt_link_source_alias("other", "prompt_template", ref) is None
    assert node_reference("My Cube", "positive_prompt") == '"My Cube".positive_prompt'


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


def test_bypassed_cube_serializes_as_comments_and_bridges_active_connections() -> None:
    """Bypassed cubes should round-trip while active connects skip over them."""

    ordered = ["A", "B", "C"]
    cubes = {
        "A": CubeState(
            cube_id="Owner/Repo/a.cube",
            version="1.0.0",
            alias="A",
            original_cube={},
            buffer=OrderedDict(
                cube_id="Owner/Repo/a.cube",
                outputs={"output.image": {}},
                nodes=OrderedDict(),
            ),
        ),
        "B": CubeState(
            cube_id="Owner/Repo/b.cube",
            version="1.0.0",
            alias="B",
            original_cube={},
            buffer=OrderedDict(
                cube_id="Owner/Repo/b.cube",
                inputs={"input.image": {}},
                outputs={"output.image": {}},
                nodes=OrderedDict(
                    prompt={"inputs": OrderedDict(text="kept while muted")}
                ),
            ),
            bypassed=True,
        ),
        "C": CubeState(
            cube_id="Owner/Repo/c.cube",
            version="1.0.0",
            alias="C",
            original_cube={},
            buffer=OrderedDict(
                cube_id="Owner/Repo/c.cube",
                inputs={"input.image": {}},
                nodes=OrderedDict(),
            ),
        ),
    }

    script = serialize_sugar_script(strip_recipe_buffers(ordered, cubes), ordered)
    parsed = parse_sugar_script_document(script)
    restored = restore_recipe_cube_state(
        "B",
        dict(parsed.buffers["B"]),
        lambda _cube_id: {"cube_id": "Owner/Repo/b.cube", "version": "1.0.0"},
    )

    assert '# bypass use "Owner/Repo/b.cube"@1.0.0 as B' in script
    assert '# bypass set B.prompt.text = "kept while muted"' in script
    assert "connect A.output.image to C.input.image" in script
    assert "connect A.output.image to B.input.image" not in script
    assert "connect B.output.image to C.input.image" not in script
    assert parsed.buffers["B"]["bypassed"] is True
    assert (
        _nested_value(parsed.buffers["B"], "nodes", "prompt", "inputs", "text")
        == "kept while muted"
    )
    assert restored.bypassed is True


def test_bypass_comments_are_recipe_state_while_human_comments_are_ignored() -> None:
    """Only `# bypass` comments should restore bypassed cube statements."""

    sha256 = "A" * 64
    parsed = parse_sugar_script_document(
        "\n".join(
            [
                "# human comment as workflow state:",
                "# bypass   use Owner/Repo/muted.cube@1.0.0 as Muted",
                '# bypass set Muted.prompt.model = "checkpoint.safetensors"',
                f"# bypass # sha256 {sha256}",
                "",
            ]
        )
    )

    assert list(parsed.buffers) == ["Muted"]
    assert parsed.buffers["Muted"]["bypassed"] is True
    assert (
        _nested_value(parsed.buffers["Muted"], "nodes", "prompt", "inputs", "model")
        == "checkpoint.safetensors"
    )
    assert parsed.model_hashes_by_field[("Muted", "prompt", "model")] == sha256


def test_serialize_sugar_script_serializes_live_only_node_input() -> None:
    """Buffers may contain current Comfy fields absent from old cube definitions."""

    ordered = ["Demo"]
    stripped = {
        "Demo": OrderedDict(
            cube_id="Owner/Repo/demo.cube",
            nodes={
                "processor": {
                    "class_type": "UpdatedNode",
                    "inputs": {"new_widget": "chosen value"},
                }
            },
        )
    }

    script = serialize_sugar_script(stripped, ordered, global_overrides=None)

    assert 'set Demo.processor.new_widget = "chosen value"' in script


def test_serialize_sugar_script_orders_positive_prompt_before_negative_prompt() -> None:
    """Prompt set lines should serialize positive prompt fields before negative peers."""

    ordered = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="X",
            nodes=OrderedDict(
                (
                    (
                        "negative_prompt",
                        {
                            "label": "negative prompt",
                            "inputs": {"prompt_template": "low quality"},
                        },
                    ),
                    (
                        "positive_prompt",
                        {
                            "label": "positive prompt",
                            "inputs": {"prompt_template": "subject"},
                        },
                    ),
                    (
                        "schedule",
                        {
                            "inputs": OrderedDict(
                                (
                                    ("negative_prompt", "bad"),
                                    ("positive_prompt", "good"),
                                )
                            )
                        },
                    ),
                )
            ),
        )
    }

    script = serialize_sugar_script(stripped, ordered, global_overrides=None)

    assert script.index("set A.positive_prompt.prompt_template") < script.index(
        "set A.negative_prompt.prompt_template"
    )
    assert script.index('set A.schedule.positive_prompt = "good"') < script.index(
        'set A.schedule.negative_prompt = "bad"'
    )


def test_parse_sugar_script_preserves_live_only_node_input() -> None:
    """Parsing should keep known alias/node inputs without cube schema authority."""

    parsed = parse_sugar_script_document(
        "\n".join(
            [
                'use "Owner/Repo/demo.cube" as Demo',
                'set Demo.processor.new_widget = "chosen value"',
                "",
            ]
        )
    )

    assert (
        _nested_value(
            parsed.buffers["Demo"], "nodes", "processor", "inputs", "new_widget"
        )
        == "chosen value"
    )


def test_serialize_sugar_script_escapes_single_line_backslashes_roundtrip() -> None:
    """Single-line node string literals should round-trip with literal backslashes."""

    ordered = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="X",
            nodes={
                "checkpoint": {
                    "inputs": {"ckpt_name": r"Flux\flux1-dev-bnb-nf4.safetensors"}
                }
            },
        )
    }

    script = serialize_sugar_script(stripped, ordered, None)

    assert (
        'set A.checkpoint.ckpt_name = "Flux\\\\flux1-dev-bnb-nf4.safetensors"' in script
    )
    parsed = parse_sugar_script_document(script).buffers
    assert (
        _nested_value(parsed["A"], "nodes", "checkpoint", "inputs", "ckpt_name")
        == r"Flux\flux1-dev-bnb-nf4.safetensors"
    )


def test_serialize_sugar_script_serializes_model_hash_comment() -> None:
    """Model hash metadata should serialize directly below its field set line."""

    ordered = ["A"]
    sha256 = "a" * 64
    stripped = {
        "A": OrderedDict(
            cube_id="X",
            nodes={"checkpoint": {"inputs": {"ckpt_name": "base.safetensors"}}},
        )
    }

    script = serialize_sugar_script(
        stripped,
        ordered,
        model_hashes_by_field={("A", "checkpoint", "ckpt_name"): sha256},
    )

    assert (
        f'set A.checkpoint.ckpt_name = "base.safetensors"\n# sha256 {sha256.upper()}'
    ) in script


def test_serialize_sugar_script_serializes_prompt_lora_hash_comments() -> None:
    """Inline LoRA hash metadata should serialize below the prompt field set line."""

    ordered = ["A"]
    first_sha256 = "a" * 64
    second_sha256 = "b" * 64
    stripped = {
        "A": OrderedDict(
            cube_id="X",
            nodes={
                "prompt": {"inputs": {"text": "<lora:one:1.00> <lora:folder/two:2.00>"}}
            },
        )
    }

    script = serialize_sugar_script(
        stripped,
        ordered,
        prompt_lora_hashes_by_field={
            ("A", "prompt", "text"): OrderedDict(
                (
                    ("one", first_sha256),
                    ("folder/two", second_sha256),
                )
            )
        },
    )

    assert (
        'set A.prompt.text = "<lora:one:1.00> <lora:folder/two:2.00>"\n'
        f'# lora_sha256 {{"name":"one","sha256":"{first_sha256.upper()}"}}\n'
        f'# lora_sha256 {{"name":"folder/two","sha256":"{second_sha256.upper()}"}}'
    ) in script


def test_parse_sugar_script_model_hash_comment_metadata() -> None:
    """Adjacent SHA256 comments should parse as field metadata only."""

    sha256 = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
    parsed = parse_sugar_script_document(
        "\n".join(
            [
                "use X as A",
                'set A.checkpoint.ckpt_name = "base.safetensors"',
                f"# sha256 {sha256}",
                "",
            ]
        )
    )

    assert (
        _nested_value(parsed.buffers["A"], "nodes", "checkpoint", "inputs", "ckpt_name")
        == "base.safetensors"
    )
    assert parsed.model_hashes_by_field == {("A", "checkpoint", "ckpt_name"): sha256}


def test_parse_sugar_script_prompt_lora_hash_comment_metadata() -> None:
    """Adjacent inline LoRA SHA256 comments should parse as prompt-field metadata."""

    first_sha256 = "A" * 64
    second_sha256 = "B" * 64
    parsed = parse_sugar_script_document(
        "\n".join(
            [
                "use X as A",
                'set A.prompt.text = "<lora:one:1.00> <lora:folder/two:2.00>"',
                f'# lora_sha256 {{"sha256":"{first_sha256}","name":"one"}}',
                f'# lora_sha256 {{"name":"folder/two","sha256":"{second_sha256}"}}',
                "",
            ]
        )
    )

    assert parsed.prompt_lora_hashes_by_field == {
        ("A", "prompt", "text"): OrderedDict(
            (
                ("one", first_sha256),
                ("folder/two", second_sha256),
            )
        )
    }


def test_parse_sugar_script_keeps_field_and_prompt_lora_hash_comments() -> None:
    """Field and inline LoRA hash comments should coexist below one set line."""

    field_sha256 = "A" * 64
    lora_sha256 = "B" * 64
    parsed = parse_sugar_script_document(
        "\n".join(
            [
                "use X as A",
                'set A.prompt.text = "<lora:one:1.00>"',
                f"# sha256 {field_sha256}",
                f'# lora_sha256 {{"name":"one","sha256":"{lora_sha256}"}}',
                "",
            ]
        )
    )

    assert parsed.model_hashes_by_field == {("A", "prompt", "text"): field_sha256}
    assert parsed.prompt_lora_hashes_by_field == {
        ("A", "prompt", "text"): OrderedDict((("one", lora_sha256),))
    }


def test_parse_sugar_script_ignores_non_adjacent_model_hash_comment() -> None:
    """SHA256 comments should apply only to the immediately preceding set line."""

    sha256 = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
    parsed = parse_sugar_script_document(
        "\n".join(
            [
                "use X as A",
                'set A.checkpoint.ckpt_name = "base.safetensors"',
                "",
                f"# sha256 {sha256}",
                "",
            ]
        )
    )

    assert parsed.model_hashes_by_field == {}


def test_parse_sugar_script_ignores_non_adjacent_prompt_lora_hash_comment() -> None:
    """Inline LoRA hash comments should apply only to adjacent set lines."""

    sha256 = "A" * 64
    parsed = parse_sugar_script_document(
        "\n".join(
            [
                "use X as A",
                'set A.prompt.text = "<lora:one:1.00>"',
                "",
                f'# lora_sha256 {{"name":"one","sha256":"{sha256}"}}',
                "",
            ]
        )
    )

    assert parsed.prompt_lora_hashes_by_field == {}


def test_parse_sugar_script_ignores_malformed_prompt_lora_hash_comments() -> None:
    """Malformed inline LoRA hash comments should not block valid adjacent rows."""

    sha256 = "A" * 64
    parsed = parse_sugar_script_document(
        "\n".join(
            [
                "use X as A",
                'set A.prompt.text = "<lora:one:1.00>"',
                "# lora_sha256 not-json",
                f'# lora_sha256 {{"name":"","sha256":"{sha256}"}}',
                '# lora_sha256 {"name":"bad","sha256":"not-a-sha"}',
                f'# lora_sha256 {{"name":"one","sha256":"{sha256.lower()}"}}',
                "",
            ]
        )
    )

    assert parsed.prompt_lora_hashes_by_field == {
        ("A", "prompt", "text"): OrderedDict((("one", sha256),))
    }


def test_serialize_sugar_script_serializes_pinned_cube_version() -> None:
    """Pinned cube instances should carry their selected version in Sugar text."""

    ordered = ["Text To Image"]
    cube = CubeState(
        cube_id="Owner/Repo/Text to Image.cube",
        version="1.8.0",
        alias="Text To Image",
        original_cube={},
        buffer=OrderedDict(cube_id="Owner/Repo/Text to Image.cube", nodes={}),
    )

    script = serialize_sugar_script(
        strip_recipe_buffers(ordered, {"Text To Image": cube}), ordered
    )

    assert 'use "Owner/Repo/Text to Image.cube"@1.8.0 as "Text To Image"' in script


def test_serialize_sugar_script_omits_follow_latest_version_pin() -> None:
    """Follow-latest cube instances should compile as versionless Sugar uses."""

    ordered = ["Text To Image"]
    cube = CubeState(
        cube_id="Owner/Repo/Text to Image.cube",
        version="1.8.0",
        alias="Text To Image",
        original_cube={},
        buffer=OrderedDict(cube_id="Owner/Repo/Text to Image.cube", nodes={}),
        update_policy=CubeUpdatePolicy.FOLLOW_LATEST,
    )

    script = serialize_sugar_script(
        strip_recipe_buffers(ordered, {"Text To Image": cube}), ordered
    )

    assert 'use "Owner/Repo/Text to Image.cube" as "Text To Image"' in script
    assert "@1.8.0" not in script


def test_serialize_sugar_script_serializes_two_versions_of_same_cube() -> None:
    """Distinct aliases of one cube id should keep their own version pins."""

    ordered = ["Old Text To Image", "New Text To Image"]
    cube_id = "Owner/Repo/Text to Image.cube"
    cubes = {
        "Old Text To Image": CubeState(
            cube_id=cube_id,
            version="1.7.0",
            alias="Old Text To Image",
            original_cube={},
            buffer=OrderedDict(cube_id=cube_id, nodes={}),
        ),
        "New Text To Image": CubeState(
            cube_id=cube_id,
            version="1.8.0",
            alias="New Text To Image",
            original_cube={},
            buffer=OrderedDict(cube_id=cube_id, nodes={}),
        ),
    }

    script = serialize_sugar_script(strip_recipe_buffers(ordered, cubes), ordered)

    assert 'use "Owner/Repo/Text to Image.cube"@1.7.0 as "Old Text To Image"' in script
    assert 'use "Owner/Repo/Text to Image.cube"@1.8.0 as "New Text To Image"' in script


def test_serialize_sugar_script_quotes_special_version_pin() -> None:
    """Version pins outside Sugar bare token rules should be quoted after @."""

    ordered = ["Demo"]
    cube = CubeState(
        cube_id="Owner/Repo/demo.cube",
        version="1.8.0-beta 1",
        alias="Demo",
        original_cube={},
        buffer=OrderedDict(cube_id="Owner/Repo/demo.cube", nodes={}),
    )

    script = serialize_sugar_script(
        strip_recipe_buffers(ordered, {"Demo": cube}), ordered
    )
    parsed = parse_sugar_script_document(script)

    assert 'use "Owner/Repo/demo.cube"@"1.8.0-beta 1" as Demo' in script
    assert parsed.buffers["Demo"]["version"] == "1.8.0-beta 1"


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


def test_links_and_disabled_nodes_export_and_parse() -> None:
    """Linked and disabled node state should serialize and parse deterministically."""

    ordered_aliases = ["A", "Alias With Space"]
    stripped_buffers = {
        "A": OrderedDict(
            cube_id="Text To Image",
            nodes={
                "sampler": {"inputs": {"sampler_name": "euler"}},
                "positive_prompt": {"inputs": {"prompt_template": "base"}},
            },
            outputs={"image": True},
            inputs={},
        ),
        "Alias With Space": OrderedDict(
            cube_id="Fancy Consumer",
            nodes={
                "use_sampler": {
                    "inputs": {"sampler_name": ""},
                    "sampler_link": {"from_cube": "A", "from_node": "sampler"},
                },
                "use_scheduler": {
                    "inputs": {"scheduler": ""},
                    "scheduler_link": {"from_cube": "A", "from_node": "sampler"},
                },
                "negative_prompt": {
                    "inputs": {"prompt_template": "local dormant"},
                    "node_link": {"from_cube": "A", "from_node": "negative_prompt"},
                },
                "disabled node": {
                    "enabled": False,
                    "inputs": {},
                },
            },
            inputs={"input_image": True},
        ),
    }

    script = serialize_sugar_script(
        stripped_buffers, ordered_aliases, global_overrides=None
    )

    # Disable line with quoting should be emitted once.
    disable_line = 'disable "Alias With Space"."disabled node"'
    assert disable_line in script
    assert script.count(disable_line) == 1

    # Sampler/scheduler links are emitted with field references.
    assert (
        'set "Alias With Space".use_sampler.sampler_name = A.sampler.sampler_name'
        in script
    )
    assert (
        'set "Alias With Space".use_scheduler.scheduler = A.sampler.scheduler' in script
    )
    # Node links are emitted with whole-node references while preserving local inputs.
    assert 'set "Alias With Space".negative_prompt = A.negative_prompt' in script
    assert (
        'set "Alias With Space".negative_prompt.prompt_template = "local dormant"'
        in script
    )

    # Parse back
    parsed_document = parse_sugar_script_document(script)
    assert parsed_document.global_overrides == {}

    b = parsed_document.buffers["Alias With Space"]
    assert _nested_value(b, "nodes", "use_sampler", "sampler_link") == {
        "from_cube": "A",
        "from_node": "sampler",
    }
    assert "sampler_name" not in _nested_mapping(b, "nodes", "use_sampler", "inputs")

    assert _nested_value(b, "nodes", "use_scheduler", "scheduler_link") == {
        "from_cube": "A",
        "from_node": "sampler",
    }
    assert "scheduler" not in _nested_mapping(b, "nodes", "use_scheduler", "inputs")

    assert _nested_value(b, "nodes", "negative_prompt", "node_link") == {
        "from_cube": "A",
        "from_node": "negative_prompt",
    }
    assert (
        _nested_value(b, "nodes", "negative_prompt", "inputs", "prompt_template")
        == "local dormant"
    )
    # Disabled node preserved
    assert _nested_value(b, "nodes", "disabled node", "enabled") is False


def test_connect_lines_and_quoting() -> None:
    """Connect statements should quote aliases and endpoint labels when required."""

    ordered_aliases = ["From Cube", "To/Cube"]
    stripped = {
        "From Cube": OrderedDict(
            cube_id="X", nodes={}, outputs={"out name": True}, inputs={}
        ),
        "To/Cube": OrderedDict(cube_id="Y", nodes={}, inputs={"in name": True}),
    }
    script = serialize_sugar_script(stripped, ordered_aliases, None)
    assert 'connect "From Cube"."out name" to "To/Cube"."in name"' in script


def test_policy_disabled_nodes_emit_disable_without_inputs() -> None:
    """Resolved-disabled nodes should not contribute executable input settings."""

    ordered_aliases = ["Text", "Upscale"]
    stripped = {
        "Text": OrderedDict(
            cube_id="Text",
            nodes={
                "checkpoint": {
                    "inputs": {"ckpt_name": "base.safetensors"},
                }
            },
        ),
        "Upscale": OrderedDict(
            cube_id="Upscale",
            nodes={
                "checkpoint": {
                    "inputs": {"ckpt_name": "hidden-bad.safetensors"},
                },
                "load_upscale_model": {
                    "inputs": {"model_name": "R-ESRGAN 4x+ Anime6B.pth"},
                },
            },
        ),
    }

    script = serialize_sugar_script(
        stripped,
        ordered_aliases,
        global_overrides=None,
        disabled_node_keys_by_alias={"Upscale": ("checkpoint",)},
    )

    assert "disable Upscale.checkpoint" in script
    assert "hidden-bad.safetensors" not in script
    assert (
        'set Upscale.load_upscale_model.model_name = "R-ESRGAN 4x+ Anime6B.pth"'
        in script
    )


def test_revealed_disabled_nodes_export_and_parse_independent_state() -> None:
    """Reveal metadata and disable directives should round-trip independently."""

    ordered_aliases = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="Overrides",
            nodes={
                "vae": {
                    "revealed": True,
                    "enabled": False,
                    "inputs": {"vae_name": "ignored.safetensors"},
                },
            },
        ),
    }

    script = serialize_sugar_script(stripped, ordered_aliases, global_overrides=None)

    assert '# node_revealed {"alias":"A","node":"vae"}' in script
    assert "disable A.vae" in script
    assert "ignored.safetensors" not in script

    parsed = parse_sugar_script_document(script).buffers
    node = _nested_mapping(parsed["A"], "nodes", "vae")
    assert node["revealed"] is True
    assert node["enabled"] is False


def test_reveal_metadata_is_omitted_from_generation_compile_scripts() -> None:
    """Generation serialization should not send editor reveal metadata to the compiler."""

    ordered_aliases = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="Overrides",
            nodes={
                "vae": {
                    "revealed": True,
                    "inputs": {"vae_name": "ignored.safetensors"},
                },
            },
        ),
    }

    script = serialize_sugar_script(
        stripped,
        ordered_aliases,
        global_overrides=None,
        disabled_node_keys_by_alias={"A": ("vae",)},
    )

    assert "node_revealed" not in script
    assert "reveal A.vae" not in script
    assert "disable A.vae" in script
    assert "ignored.safetensors" not in script


def test_explicit_enabled_state_is_metadata_not_sugar_statement() -> None:
    """Explicit enabled state should round-trip without inventing Sugar syntax."""

    ordered_aliases = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="Overrides",
            nodes={
                "vae": {
                    "revealed": True,
                    "enabled": True,
                    "inputs": {"vae_name": "override.safetensors"},
                },
            },
        ),
    }

    script = serialize_sugar_script(stripped, ordered_aliases, global_overrides=None)

    assert "enable A.vae" not in script
    assert '# node_enabled {"alias":"A","enabled":true,"node":"vae"}' in script
    assert '# node_revealed {"alias":"A","node":"vae"}' in script

    parsed = parse_sugar_script_document(script).buffers
    node = _nested_mapping(parsed["A"], "nodes", "vae")
    assert node["enabled"] is True
    assert node["revealed"] is True


def test_explicit_enabled_metadata_is_omitted_from_generation_compile_scripts() -> None:
    """Generation serialization should rely on absence of disable for enabled nodes."""

    ordered_aliases = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="Overrides",
            nodes={
                "vae": {
                    "revealed": True,
                    "enabled": True,
                    "inputs": {"vae_name": "override.safetensors"},
                },
            },
        ),
    }

    script = serialize_sugar_script(
        stripped,
        ordered_aliases,
        global_overrides=None,
        disabled_node_keys_by_alias={},
    )

    assert "enable A.vae" not in script
    assert "node_enabled" not in script
    assert "node_revealed" not in script
    assert "disable A.vae" not in script
    assert 'set A.vae.vae_name = "override.safetensors"' in script


def test_generation_compile_uses_activation_deltas_for_authored_bypass_nodes() -> None:
    """Generation activation commands should be deltas from authored defaults."""

    ordered_aliases = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="Overrides",
            nodes={
                "vae": {
                    "mode": 4,
                    "revealed": True,
                    "enabled": True,
                    "inputs": {"vae_name": "override.safetensors"},
                },
                "preview": {
                    "mode": 4,
                    "revealed": True,
                    "inputs": {"strength": 0.75},
                },
            },
        ),
    }

    script = serialize_sugar_script(
        stripped,
        ordered_aliases,
        global_overrides=None,
        enabled_node_keys_by_alias={"A": ("vae",)},
        disabled_node_keys_by_alias={"A": ("preview",)},
    )

    assert "node_enabled" not in script
    assert "node_revealed" not in script
    assert "enable A.vae" in script
    assert "disable A.vae" not in script
    assert "disable A.preview" not in script
    assert 'set A.vae.vae_name = "override.safetensors"' in script
    assert "set A.preview.strength" not in script


def test_generation_serialization_does_not_disable_hidden_active_schedule_node() -> (
    None
):
    """Hidden active infrastructure nodes should not receive disable commands."""

    ordered_aliases = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="Demo",
            nodes={
                "schedule_encode_prompts": {
                    "class_type": (
                        "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                    ),
                    "inputs": {"encode_style": ""},
                    "label": "Schedule & Encode Prompts",
                },
            },
        ),
    }

    script = serialize_sugar_script(
        stripped,
        ordered_aliases,
        global_overrides=None,
        disabled_node_keys_by_alias={},
    )

    assert "disable A" not in script
    assert 'set A.schedule_encode_prompts.encode_style = ""' in script


def test_strip_recipe_buffers_preserves_revealed_node_metadata() -> None:
    """Stripped recipe buffers should retain authored and editor node metadata."""

    ordered = ["A"]
    original_buffer: JsonObject = OrderedDict(
        cube_id="X",
        nodes={"vae": {"mode": 4, "revealed": True, "enabled": False, "inputs": {}}},
    )
    cs = CubeState(
        cube_id="X",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer=original_buffer,
    )

    stripped = strip_recipe_buffers(ordered, {"A": cs})

    assert _nested_value(stripped["A"], "nodes", "vae", "revealed") is True
    assert _nested_value(stripped["A"], "nodes", "vae", "enabled") is False
    assert _nested_value(stripped["A"], "nodes", "vae", "mode") == 4


def test_connect_lines_with_standardized_io_names() -> None:
    """Standard input/output prefixes should produce canonical connect paths."""

    ordered_aliases = ["Text_to_Image", "Diffusion_Upscale"]
    stripped = {
        "Text_to_Image": OrderedDict(
            cube_id="Text_to_Image",
            nodes={},
            outputs={"text_to_image.output.image": True},
            inputs={},
        ),
        "Diffusion_Upscale": OrderedDict(
            cube_id="Diffusion_Upscale",
            nodes={},
            outputs={},
            inputs={"diffusion_upscale.input.image": True},
        ),
    }
    script = serialize_sugar_script(stripped, ordered_aliases, None)
    assert (
        "connect Text_to_Image.output.image to Diffusion_Upscale.input.image" in script
    )


def test_prompt_link_with_quoted_alias_names() -> None:
    """Prompt node links should preserve aliases that require quoted segments."""

    ordered = ["Ali as", "Other Alias"]
    stripped = {
        "Ali as": OrderedDict(
            cube_id="Text To Image",
            nodes={
                "positive_prompt": {
                    "inputs": {"prompt_template": ""},
                    "node_link": {
                        "from_cube": "Other Alias",
                        "from_node": "positive_prompt",
                    },
                }
            },
        ),
        "Other Alias": OrderedDict(
            cube_id="Upstream",
            nodes={"positive_prompt": {"inputs": {"prompt_template": "seed"}}},
        ),
    }
    script = serialize_sugar_script(stripped, ordered, None)
    assert 'set "Ali as".positive_prompt = "Other Alias".positive_prompt' in script


def test_multiline_values_roundtrip() -> None:
    """Safe multiline values should retain readable triple-quoted syntax."""

    ordered = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="X",
            nodes={"positive_prompt": {"inputs": {"prompt_template": "line1\nline2"}}},
        )
    }
    script = serialize_sugar_script(stripped, ordered, None)
    assert '"""line1\nline2"""' in script
    parsed = parse_sugar_script_document(script).buffers
    assert (
        _nested_value(
            parsed["A"], "nodes", "positive_prompt", "inputs", "prompt_template"
        )
        == "line1\nline2"
    )


@pytest.mark.parametrize(
    "prompt",
    [
        'line1\nline2"',
        'line1\nline2""',
        'line1\nline2"""',
        'line1\nembedded """ delimiter',
        'line1\r\nline2"',
        'line1\nbackslash before quote \\"',
        'line1\nprompt escapes \\(literal\\)"',
        'line1\nUnicode café 猫"',
        'line1\ncolumn\tvalue"',
    ],
)
def test_multiline_prompt_delimiter_collisions_use_safe_literals(
    prompt: str,
) -> None:
    """Delimiter-sensitive prompts should emit valid escaped Sugar literals."""

    ordered = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="X",
            nodes={"positive_prompt": {"inputs": {"prompt_template": prompt}}},
        )
    }

    script = serialize_sugar_script(stripped, ordered, None)

    prompt_line = next(
        line
        for line in script.splitlines()
        if line.startswith("set A.positive_prompt.prompt_template = ")
    )
    assert "\\n" in prompt_line
    assert ' = "' in prompt_line
    assert '= """' not in prompt_line
    parsed = parse_sugar_script_document(script).buffers
    assert (
        _nested_value(
            parsed["A"], "nodes", "positive_prompt", "inputs", "prompt_template"
        )
        == prompt
    )


def test_global_overrides_skip_local_set_lines() -> None:
    """Global overrides should suppress duplicate local field assignments."""

    ordered = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="X",
            nodes={"sampler": {"inputs": {"steps": 20, "sampler_name": "euler"}}},
        )
    }
    script = serialize_sugar_script(
        stripped, ordered, {"steps": {"value": 999, "mode": "global"}}
    )
    # Global override present
    assert "set *.*.steps = 999" in script
    # Node-level steps should be skipped
    assert "set A.sampler.steps" not in script


def test_global_overrides_string_values_are_quoted_for_dsl_literals() -> None:
    """String override values should emit explicit Sugar string literals."""

    ordered = ["A"]
    stripped = {
        "A": OrderedDict(cube_id="X", nodes={"ksampler": {"inputs": {}}}),
    }
    script = serialize_sugar_script(
        stripped, ordered, {"scheduler": {"value": "normal", "mode": "global"}}
    )
    assert 'set *.*.scheduler = "normal"' in script


def test_global_overrides_use_single_blank_line_before_local_sets() -> None:
    """Wildcard overrides should not inherit spacing from empty metadata sections."""

    ordered = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="X",
            nodes={"sampler": {"inputs": {"seed": 1, "foo": 2}}},
        )
    }

    script = serialize_sugar_script(
        stripped,
        ordered,
        {"seed": {"value": 99, "mode": "global"}},
    )

    assert script == ("use X as A\n\nset *.*.seed = 99\n\nset A.sampler.foo = 2\n")


def test_global_override_selections_roundtrip_as_metadata_comments() -> None:
    """Authored override menu selections should persist as non-executable metadata."""

    ordered = ["A"]
    stripped = {
        "A": OrderedDict(cube_id="X", nodes={"ksampler": {"inputs": {}}}),
    }

    script = serialize_sugar_script(
        stripped,
        ordered,
        {"cfg": {"value": 7.0, "mode": "global"}},
        global_override_selections={"seed": False, "cfg": True},
    )
    parsed = parse_sugar_script_document(script)

    assert '# global_override_selection {"key":"seed","selected":false}' in script
    assert '# global_override_selection {"key":"cfg","selected":true}' in script
    assert parsed.global_override_selections == {"seed": False, "cfg": True}
    assert parsed.global_overrides == {"cfg": {"value": 7.0, "mode": "global"}}


def test_inactive_global_override_selection_does_not_skip_local_set_lines() -> None:
    """Inactive selections are UI intent and should not suppress local values."""

    ordered = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="X",
            nodes={"sampler": {"inputs": {"seed": 12}}},
        )
    }

    script = serialize_sugar_script(
        stripped,
        ordered,
        global_overrides={},
        global_override_selections={"seed": False},
    )

    assert "set A.sampler.seed = 12" in script


def test_partial_global_override_scope_emits_metadata_and_participant_set_lines() -> (
    None
):
    """Partial override scopes should avoid wildcard Sugar execution."""

    ordered = ["A", "B"]
    stripped = {
        "A": OrderedDict(
            cube_id="X",
            nodes={"sampler": {"inputs": {"sampler_name": "euler"}}},
        ),
        "B": OrderedDict(
            cube_id="Y",
            nodes={"sampler": {"inputs": {"sampler_name": "ddim"}}},
        ),
    }

    script = serialize_sugar_script(
        stripped,
        ordered,
        global_overrides={"sampler_name": {"value": "heun", "mode": "global"}},
        global_override_scopes={
            "sampler_name": GlobalOverrideSerializationScope(
                override_key="sampler_name",
                value="heun",
                mode="global",
                full_participation=False,
                participant_fields=frozenset({("A", "sampler", "sampler_name")}),
            )
        },
    )

    assert "set *.*.sampler_name" not in script
    assert (
        '# global_override_value {"key":"sampler_name","mode":"global","value":"heun"}'
        in script
    )
    assert 'set A.sampler.sampler_name = "heun"' in script
    assert 'set B.sampler.sampler_name = "ddim"' in script


def test_full_encode_style_scope_serializes_wildcard_and_preserves_schedule_link() -> (
    None
):
    """Encode style overrides should serialize as wildcard without schedule set lines."""

    ordered = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="X",
            nodes={
                "prompt_encode_style": {
                    "label": "Prompt Encode Style",
                    "inputs": {"encode_style": "A1111"},
                },
                "schedule_encode_prompts": {
                    "label": "Schedule & Encode Prompts",
                    "inputs": {"encode_style": ["prompt_encode_style", 0]},
                },
            },
        ),
    }

    script = serialize_sugar_script(
        stripped,
        ordered,
        global_overrides={"encode_style": {"value": "Comfy", "mode": "global"}},
        global_override_scopes={
            "encode_style": GlobalOverrideSerializationScope(
                override_key="encode_style",
                value="Comfy",
                mode="global",
                full_participation=True,
                participant_fields=frozenset(
                    {("A", "prompt_encode_style", "encode_style")}
                ),
            )
        },
    )

    assert 'set *.*.encode_style = "Comfy"' in script
    assert "# global_override_value" not in script
    assert "prompt_encode_style.encode_style" not in script
    assert "Schedule & Encode Prompts" not in script


def test_full_encode_style_scope_omits_stale_schedule_literal() -> None:
    """Wildcard encode style serialization should not leak stale infrastructure literals."""

    ordered = ["A"]
    stripped = {
        "A": OrderedDict(
            cube_id="X",
            nodes={
                "prompt_encode_style": {
                    "label": "Prompt Encode Style",
                    "inputs": {"encode_style": "A1111"},
                },
                "schedule_encode_prompts": {
                    "label": "Schedule & Encode Prompts",
                    "inputs": {"encode_style": "A1111"},
                },
            },
        ),
    }

    script = serialize_sugar_script(
        stripped,
        ordered,
        global_overrides={"encode_style": {"value": "A1111", "mode": "global"}},
        global_override_scopes={
            "encode_style": GlobalOverrideSerializationScope(
                override_key="encode_style",
                value="A1111",
                mode="global",
                full_participation=True,
                participant_fields=frozenset(
                    {("A", "prompt_encode_style", "encode_style")}
                ),
            )
        },
    )

    assert 'set *.*.encode_style = "A1111"' in script
    assert "prompt_encode_style.encode_style" not in script
    assert "Schedule & Encode Prompts" not in script
    assert "schedule_encode_prompts" not in script


def test_global_override_value_metadata_roundtrips_and_wildcard_wins() -> None:
    """Partial-scope metadata should restore values unless a wildcard set overrides it."""

    parsed = parse_sugar_script_document(
        "\n".join(
            [
                "use X as A",
                '# global_override_value {"key":"sampler_name","value":"euler"}',
                'set *.*.sampler_name = "heun"',
                "",
            ]
        )
    )

    assert parsed.global_overrides == {
        "sampler_name": {"value": "heun", "mode": "global"}
    }


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


def test_versionless_use_round_trips_follow_latest_policy() -> None:
    """Versionless Sugar use statements should preserve follow-latest policy."""

    ordered = ["A"]
    cube = CubeState(
        cube_id="Owner/Repo/demo.cube",
        version="2.0",
        alias="A",
        original_cube={"cube_id": "Owner/Repo/demo.cube", "version": "2.0"},
        buffer=OrderedDict(cube_id="Owner/Repo/demo.cube", nodes={}),
        update_policy=CubeUpdatePolicy.FOLLOW_LATEST,
    )

    stripped = strip_recipe_buffers(ordered, {"A": cube})
    script = serialize_sugar_script(stripped, ordered)
    parsed = parse_sugar_script_document(script)
    restored = restore_recipe_cube_state(
        "A",
        dict(parsed.buffers["A"]),
        lambda _cube_id: {"cube_id": "Owner/Repo/demo.cube", "version": "2.0"},
    )

    assert 'use "Owner/Repo/demo.cube" as A' in script
    assert "@2.0" not in script
    assert parsed.buffers["A"]["update_policy"] == "follow_latest"
    assert "version" not in parsed.buffers["A"]
    assert restored.update_policy == CubeUpdatePolicy.FOLLOW_LATEST
    assert restored.version == "2.0"


def test_old_cube_metadata_comment_does_not_override_use_intent() -> None:
    """Old Substitute metadata comments should be inert recipe comments."""

    parsed = parse_sugar_script_document(
        "\n".join(
            [
                'use "Owner/Repo/demo.cube" as A',
                '# cube_metadata {"alias":"A","update_policy":"pinned","version":"1.0"}',
                "",
            ]
        )
    )
    restored = restore_recipe_cube_state(
        "A",
        dict(parsed.buffers["A"]),
        lambda _cube_id: {"cube_id": "Owner/Repo/demo.cube", "version": "2.0"},
    )

    assert "cube_metadata" not in parsed.buffers["A"]
    assert restored.update_policy == CubeUpdatePolicy.FOLLOW_LATEST
    assert restored.version == "2.0"


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


def test_parse_whole_node_link_assignment_preserves_dormant_local_values() -> None:
    """Whole-node Sugar links should parse into canonical node-link metadata."""

    script = "\n".join(
        [
            "use txt as A",
            "use up as B",
            "set B.vectorscopecc.brightness = 0.75",
            "set B.vectorscopecc = A.vectorscopecc",
            "",
        ]
    )

    parsed = parse_sugar_script_document(script).buffers

    node = _nested_mapping(parsed["B"], "nodes", "vectorscopecc")
    assert _nested_value(node, "inputs", "brightness") == 0.75
    assert node["node_link"] == {"from_cube": "A", "from_node": "vectorscopecc"}


def test_parse_legacy_prompt_field_reference_as_node_link() -> None:
    """Old prompt field reference syntax should load as canonical node-link metadata."""

    script = "\n".join(
        [
            "use txt as A",
            "use up as B",
            "set B.positive_prompt.prompt_template = A.positive_prompt.prompt_template",
            "",
        ]
    )

    parsed = parse_sugar_script_document(script).buffers

    node = _nested_mapping(parsed["B"], "nodes", "positive_prompt")
    assert node["node_link"] == {"from_cube": "A", "from_node": "positive_prompt"}
    assert _nested_value(node, "inputs", "prompt_template") == ""
