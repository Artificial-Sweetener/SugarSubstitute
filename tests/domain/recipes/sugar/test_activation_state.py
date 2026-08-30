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

"""Sugar recipe activation-state contracts."""

from collections import OrderedDict


from substitute.domain.common import JsonObject
from substitute.domain.recipes.recipe_buffers import (
    restore_recipe_cube_state,
    strip_recipe_buffers,
)
from substitute.domain.recipes.sugar_script_parser import (
    parse_sugar_script_document,
)
from substitute.domain.workflow import CubeState
from tests.domain.recipes.sugar.serialization_support import serialize_sugar_script
from tests.domain.recipes.sugar.persistence_support import (
    _nested_mapping,
    _nested_value,
)


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
