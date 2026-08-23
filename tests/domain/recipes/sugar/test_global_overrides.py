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

"""Sugar recipe global-override contracts."""

from collections import OrderedDict


from substitute.domain.recipes.sugar_script_parser import (
    parse_sugar_script_document,
)
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from tests.domain.recipes.sugar.serialization_support import serialize_sugar_script


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
