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

"""Sugar generation-script contracts."""

from collections import OrderedDict


from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from tests.domain.recipes.sugar.serialization_support import serialize_sugar_script


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
