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

"""Sugar recipe link-reference contracts."""

from collections import OrderedDict


from substitute.domain.recipes.sugar_links import (
    node_reference,
    prompt_field_reference,
    prompt_link_source_alias,
)
from substitute.domain.recipes.sugar_script_parser import (
    parse_sugar_script_document,
)
from tests.domain.recipes.sugar.serialization_support import serialize_sugar_script
from tests.domain.recipes.sugar.persistence_support import (
    _nested_mapping,
    _nested_value,
)


def test_prompt_link_reference_and_parse() -> None:
    """Prompt and node link references should quote and parse aliases."""

    ref = prompt_field_reference("My Cube", "positive_prompt", "prompt_template")
    assert ref == '"My Cube".positive_prompt.prompt_template'

    # Must parse only for positive/negative_prompt nodes and prompt_template param
    alias = prompt_link_source_alias("positive_prompt", "prompt_template", ref)
    assert alias == "My Cube"
    assert prompt_link_source_alias("other", "prompt_template", ref) is None
    assert node_reference("My Cube", "positive_prompt") == '"My Cube".positive_prompt'


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
