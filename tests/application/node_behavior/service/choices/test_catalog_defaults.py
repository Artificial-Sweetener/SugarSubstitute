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

"""Model-catalog default resolution contracts."""

from __future__ import annotations


from substitute.application.node_behavior import (
    FieldValueSource,
)
from tests.support.node_behavior import (
    build_behavior_snapshot,
    cube_state,
)


def test_build_snapshot_canonicalizes_invalid_live_list_literals_without_dirtying() -> (
    None
):
    """Invalid live list literals should resolve in application code without dirtying cube state."""

    cube = cube_state(
        nodes={
            "checkpoint": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "legacy-model"},
            }
        },
    )
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {
                        "ckpt_name": [
                            ["model-a.safetensors", "model-b.safetensors"],
                            {"default": "model-b.safetensors"},
                        ]
                    }
                }
            }
        },
    )

    spec = snapshot.field_specs_by_alias["A"]["checkpoint"]["ckpt_name"]

    assert spec.raw_value == "legacy-model"
    assert spec.value == "model-b.safetensors"
    assert spec.value_source == FieldValueSource.LIVE_DEFAULT
    assert cube.buffer["nodes"]["checkpoint"]["inputs"]["ckpt_name"] == (
        "model-b.safetensors"
    )
    assert cube.dirty is False


def test_empty_checkpoint_catalog_blanks_stale_value_then_selects_sole_model() -> None:
    """A loaded unavailable checkpoint should blank and later adopt the only model."""

    stale_checkpoint = r"Flux\waiAniFlux_v10ForFP8.safetensors"
    available_checkpoint = r"SDXL\only-model.safetensors"
    cube = cube_state(
        nodes={
            "checkpoint": {
                "class_type": "SimpleSyrup.SimpleLoadCheckpoint",
                "inputs": {"ckpt_name": stale_checkpoint},
            }
        },
    )

    empty_snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "SimpleSyrup.SimpleLoadCheckpoint": {
                "input": {"required": {"ckpt_name": [[], {}]}},
            }
        },
    )
    empty_spec = empty_snapshot.field_specs_by_alias["A"]["checkpoint"]["ckpt_name"]

    assert empty_spec.raw_value == stale_checkpoint
    assert empty_spec.value == ""
    assert empty_spec.value_source is FieldValueSource.NO_OPTIONS
    assert cube.buffer["nodes"]["checkpoint"]["inputs"]["ckpt_name"] == ""
    assert cube.dirty is False

    one_model_snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "SimpleSyrup.SimpleLoadCheckpoint": {
                "input": {
                    "required": {
                        "ckpt_name": [[available_checkpoint], {}],
                    }
                },
            }
        },
    )
    one_model_spec = one_model_snapshot.field_specs_by_alias["A"]["checkpoint"][
        "ckpt_name"
    ]

    assert one_model_spec.raw_value == ""
    assert one_model_spec.value == available_checkpoint
    assert one_model_spec.value_source is FieldValueSource.FIRST_OPTION
    assert cube.buffer["nodes"]["checkpoint"]["inputs"]["ckpt_name"] == (
        available_checkpoint
    )
    assert cube.dirty is False


def test_empty_upscaler_catalog_blanks_stale_value_then_selects_discovered_model() -> (
    None
):
    """Every authoritative finite choice should survive zero-to-one transitions."""

    stale_model = "missing-upscaler.pth"
    available_model = "4x-AnimeSharp.pth"
    cube = cube_state(
        nodes={
            "upscale_model": {
                "class_type": "UpscaleModelLoader",
                "inputs": {"model_name": stale_model},
            }
        },
    )

    empty_snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": ["COMBO", {"options": []}],
                    }
                }
            }
        },
    )
    empty_spec = empty_snapshot.field_specs_by_alias["A"]["upscale_model"]["model_name"]

    assert empty_spec.value == ""
    assert empty_spec.value_source is FieldValueSource.NO_OPTIONS
    assert cube.buffer["nodes"]["upscale_model"]["inputs"]["model_name"] == ""
    assert cube.dirty is False

    populated_snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": ["COMBO", {"options": [available_model]}],
                    }
                }
            }
        },
    )
    populated_spec = populated_snapshot.field_specs_by_alias["A"]["upscale_model"][
        "model_name"
    ]

    assert populated_spec.value == available_model
    assert populated_spec.value_source is FieldValueSource.FIRST_OPTION
    assert cube.buffer["nodes"]["upscale_model"]["inputs"]["model_name"] == (
        available_model
    )
    assert cube.dirty is False


def test_auto_sentinel_is_not_treated_as_an_empty_model_catalog() -> None:
    """Literal non-file choices remain valid when a node also uses model folders."""

    cube = cube_state(
        nodes={
            "anima": {
                "class_type": "SimpleSyrup.SimpleLoadAnima",
                "inputs": {"resolution": "auto"},
            }
        },
    )
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "SimpleSyrup.SimpleLoadAnima": {
                "input": {
                    "required": {
                        "resolution": [["auto"], {"default": "auto"}],
                    }
                }
            }
        },
    )

    spec = snapshot.field_specs_by_alias["A"]["anima"]["resolution"]

    assert spec.value == "auto"
    assert spec.value_source is FieldValueSource.EXPLICIT
    assert cube.buffer["nodes"]["anima"]["inputs"]["resolution"] == "auto"
    assert cube.dirty is False


def test_build_snapshot_treats_restored_model_literal_as_explicit_value() -> None:
    """Hydrated model selections should reach behavior resolution as authored input."""

    restored_checkpoint = "Illustrious\\amanatsuIllustrious_v11.safetensors"
    cube = cube_state(
        nodes={
            "checkpoint": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": restored_checkpoint},
            }
        },
    )
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {
                        "ckpt_name": [
                            [
                                "Anima\\animaOfficial_preview3Base.safetensors",
                                restored_checkpoint,
                            ],
                            {
                                "default": "Anima\\animaOfficial_preview3Base.safetensors"
                            },
                        ]
                    }
                }
            }
        },
    )

    spec = snapshot.field_specs_by_alias["A"]["checkpoint"]["ckpt_name"]

    assert spec.raw_value == restored_checkpoint
    assert spec.value == restored_checkpoint
    assert spec.value_source == FieldValueSource.EXPLICIT
    assert cube.buffer["nodes"]["checkpoint"]["inputs"]["ckpt_name"] == (
        restored_checkpoint
    )
    assert cube.dirty is False
