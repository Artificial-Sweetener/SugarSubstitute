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

"""Sugar recipe field-value contracts."""

from collections import OrderedDict

import pytest

from substitute.domain.recipes.sugar_script_parser import (
    parse_sugar_script_document,
)
from tests.domain.recipes.sugar.serialization_support import serialize_sugar_script
from tests.domain.recipes.sugar.persistence_support import (
    _nested_value,
)


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
