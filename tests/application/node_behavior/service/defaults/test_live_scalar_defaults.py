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

"""Live scalar and model-default resolution contracts."""

from __future__ import annotations


from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.application.node_behavior import (
    FieldValueSource,
)
from tests.support.node_behavior import (
    DummyNodeDefinitionGateway,
    cube_state,
)


def test_loaded_cube_blank_model_combo_canonicalizes_default_without_dirtying() -> None:
    """Blank model selections become concrete when Comfy exposes a default."""

    cube = cube_state(
        nodes={
            "checkpoint": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": ""},
            }
        },
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "CheckpointLoaderSimple": {
                    "input": {
                        "required": {
                            "ckpt_name": [
                                ["only-model.safetensors"],
                                {},
                            ]
                        }
                    }
                }
            }
        )
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["checkpoint"]["ckpt_name"]
    assert spec.value == "only-model.safetensors"
    assert spec.value_source == FieldValueSource.FIRST_OPTION
    assert cube.buffer["nodes"]["checkpoint"]["inputs"]["ckpt_name"] == (
        "only-model.safetensors"
    )
    assert cube.dirty is False


def test_loaded_cube_blank_scalar_inputs_use_live_defaults_without_dirtying() -> None:
    """Loaded cube blank typed scalar literals should render live defaults."""

    cube = cube_state(
        nodes={
            "loader": {
                "class_type": "ModelLoader",
                "inputs": {
                    "blocks_to_swap": "",
                    "cache_model": "",
                },
            }
        },
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "ModelLoader": {
                    "input": {
                        "optional": {
                            "blocks_to_swap": [
                                "INT",
                                {"default": 0, "min": 0, "max": 36, "step": 1},
                            ],
                            "cache_model": ["BOOLEAN", {"default": False}],
                        }
                    }
                }
            }
        )
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    specs = snapshot.field_specs_by_alias["A"]["loader"]
    assert specs["blocks_to_swap"].value == 0
    assert specs["blocks_to_swap"].value_source == FieldValueSource.LIVE_DEFAULT
    assert specs["cache_model"].value is False
    assert specs["cache_model"].value_source == FieldValueSource.LIVE_DEFAULT
    assert cube.buffer["nodes"]["loader"]["inputs"] == {
        "blocks_to_swap": "",
        "cache_model": "",
    }
    assert cube.dirty is False


def test_loaded_cube_authored_combo_value_wins_over_live_default() -> None:
    """Loaded cube authored choices should win over live defaults."""

    cube = cube_state(
        nodes={
            "loader": {
                "class_type": "ModelLoader",
                "inputs": {"model": "authored.safetensors"},
            }
        },
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "ModelLoader": {
                    "input": {
                        "required": {
                            "model": [
                                ["live-default.safetensors", "authored.safetensors"],
                                {"default": "live-default.safetensors"},
                            ],
                        }
                    }
                }
            }
        )
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["loader"]["model"]
    assert spec.value == "authored.safetensors"
    assert spec.value_source == FieldValueSource.EXPLICIT


def test_loaded_cube_seedvr2_blank_loader_choices_use_live_defaults() -> None:
    """SeedVR2-style blank loader choices should render from live Comfy defaults."""

    cube = cube_state(
        nodes={
            "load_dit_model": {
                "class_type": "SeedVR2LoadDiTModel",
                "inputs": {
                    "model": "",
                    "device": "",
                    "offload_device": "",
                    "attention_mode": "",
                },
            }
        },
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "SeedVR2LoadDiTModel": {
                    "input": {
                        "required": {
                            "model": [
                                [
                                    "seedvr2_ema_3b-Q4_K_M.gguf",
                                    "seedvr2_ema_3b_fp8_e4m3fn.safetensors",
                                ],
                                {
                                    "default": (
                                        "seedvr2_ema_3b_fp8_e4m3fn.safetensors"
                                    ),
                                },
                            ],
                            "device": [
                                ["cuda:0"],
                                {"default": "cuda:0"},
                            ],
                            "offload_device": [
                                ["none", "cpu", "cuda:0"],
                                {"default": "none"},
                            ],
                            "attention_mode": [
                                [
                                    "sdpa",
                                    "flash_attn_2",
                                    "flash_attn_3",
                                    "sageattn_2",
                                    "sageattn_3",
                                ],
                                {"default": "sdpa"},
                            ],
                        }
                    }
                }
            }
        )
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    specs = snapshot.field_specs_by_alias["A"]["load_dit_model"]
    assert specs["model"].value == "seedvr2_ema_3b_fp8_e4m3fn.safetensors"
    assert specs["device"].value == "cuda:0"
    assert specs["offload_device"].value == "none"
    assert specs["attention_mode"].value == "sdpa"
    assert specs["model"].value_source == FieldValueSource.LIVE_DEFAULT
    assert specs["device"].value_source == FieldValueSource.LIVE_DEFAULT
    assert specs["offload_device"].value_source == FieldValueSource.LIVE_DEFAULT
    assert specs["attention_mode"].value_source == FieldValueSource.LIVE_DEFAULT
    assert cube.buffer["nodes"]["load_dit_model"]["inputs"] == {
        "model": "",
        "device": "",
        "offload_device": "",
        "attention_mode": "",
    }
    assert cube.dirty is False
