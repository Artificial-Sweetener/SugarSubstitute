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

"""Sugar recipe model-hash metadata contracts."""

from collections import OrderedDict


from substitute.domain.recipes.sugar_script_parser import (
    parse_sugar_script_document,
)
from tests.domain.recipes.sugar.serialization_support import serialize_sugar_script
from tests.domain.recipes.sugar.persistence_support import (
    _nested_value,
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
