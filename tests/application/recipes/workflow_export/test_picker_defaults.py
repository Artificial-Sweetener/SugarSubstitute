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

"""Verify runtime picker hydration for exported workflows."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import pytest

from tests.application.recipes.workflow_export.support import (
    FakeNodeDefinitionGateway,
    build_service,
)


def _compile_inputs(
    workflow_payload: dict[str, object],
    definitions: dict[str, dict[str, object]],
    *,
    sugar_script_text: str = "use Cube as txt",
) -> dict[str, Any]:
    """Compile one-node payload and return its mutable input mapping."""
    service, _repository, _compiler = build_service(
        workflow_payload,
        node_definition_gateway=FakeNodeDefinitionGateway(definitions),
    )
    payload = service.compile_workflow_payload(
        sugar_script_text=sugar_script_text,
        output_dir=Path("projects"),
    )
    node = cast(dict[str, Any], payload["1"])
    return cast(dict[str, Any], node["inputs"])


def test_compile_workflow_payload_fills_missing_classic_picker_default() -> None:
    """Hydrate an absent required picker from the live Comfy default."""
    inputs = _compile_inputs(
        {
            "out": {
                "class_type": "SugarCubes.CubeOutput",
                "inputs": {
                    "cube_id": "local/demo.cube",
                    "instance_alias": "txt",
                    "value": ["1", 0],
                },
            },
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {},
                "_meta": {
                    "substitute": {"cube_alias": "txt", "node_name": "checkpoint"}
                },
            },
        },
        {
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {
                        "ckpt_name": [
                            ["local-a.safetensors", "local-b.safetensors"],
                            {"default": "local-b.safetensors"},
                        ]
                    }
                }
            }
        },
    )

    assert inputs["ckpt_name"] == "local-b.safetensors"


def test_compile_workflow_payload_preserves_runtime_asset_picker_values() -> None:
    """Keep runtime asset references instead of substituting Comfy defaults."""
    workflow_payload: dict[str, object] = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": r"D:\Downloads\twilight-beach-original (1).png"},
            "_meta": {
                "substitute": {"cube_alias": "SDXL/Inpaint", "node_name": "load_image"}
            },
        },
        "2": {
            "class_type": "LoadImageMask",
            "inputs": {
                "image": "twilight-beach-original_(1)__ae6d5e73__load_image_as_mask.png",
                "channel": "alpha",
            },
            "_meta": {
                "substitute": {
                    "cube_alias": "SDXL/Inpaint",
                    "node_name": "load_image_as_mask",
                }
            },
        },
        "3": {
            "class_type": "SimpleSyrup.LoadMaskBatch",
            "inputs": {"image": [], "channel": "red"},
            "_meta": {
                "substitute": {
                    "cube_alias": "Anima/Prompt by Region",
                    "node_name": "load_mask_batch",
                }
            },
        },
    }
    service, _repository, _compiler = build_service(
        workflow_payload,
        node_definition_gateway=FakeNodeDefinitionGateway(
            {
                "LoadImage": {
                    "input": {
                        "required": {
                            "image": [
                                ["00282-3430329909-ad-before.png"],
                                {"default": "00282-3430329909-ad-before.png"},
                            ]
                        }
                    }
                },
                "LoadImageMask": {
                    "input": {
                        "required": {
                            "image": [
                                ["00282-3430329909-ad-before.png"],
                                {"default": "00282-3430329909-ad-before.png"},
                            ],
                            "channel": [["alpha", "red"], {"default": "alpha"}],
                        }
                    }
                },
                "SimpleSyrup.LoadMaskBatch": {
                    "input": {
                        "required": {
                            "image": [
                                ["unrelated-default.png"],
                                {"image_upload": True, "allow_batch": True},
                            ],
                            "channel": [["alpha", "red"], {"default": "alpha"}],
                        }
                    }
                },
            }
        ),
    )

    payload = service.compile_workflow_payload(
        sugar_script_text='use "inpaint" as "SDXL/Inpaint"',
        output_dir=Path("projects"),
    )

    load_image = cast(dict[str, Any], payload["1"])
    load_image_inputs = cast(dict[str, Any], load_image["inputs"])
    load_mask = cast(dict[str, Any], payload["2"])
    load_mask_inputs = cast(dict[str, Any], load_mask["inputs"])
    load_mask_batch = cast(dict[str, Any], payload["3"])
    load_mask_batch_inputs = cast(dict[str, Any], load_mask_batch["inputs"])
    assert load_image_inputs["image"] == (
        r"D:\Downloads\twilight-beach-original (1).png"
    )
    assert load_mask_inputs["image"] == (
        "twilight-beach-original_(1)__ae6d5e73__load_image_as_mask.png"
    )
    assert load_mask_inputs["channel"] == "alpha"
    assert load_mask_batch_inputs["image"] == []
    assert load_mask_batch_inputs["channel"] == "red"


def test_compile_workflow_payload_selects_sole_picker_option() -> None:
    """Select the only available model for a blank required picker."""
    inputs = _compile_inputs(
        {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": ""},
                "_meta": {
                    "substitute": {
                        "cube_alias": "SDXL/Text to Image",
                        "node_name": "checkpoint",
                    }
                },
            }
        },
        {
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {
                        "ckpt_name": [[r"Flux\flux1-dev-bnb-nf4.safetensors"], {}]
                    }
                }
            }
        },
        sugar_script_text='use "cube" as "SDXL/Text to Image"',
    )

    assert inputs["ckpt_name"] == r"Flux\flux1-dev-bnb-nf4.safetensors"


def test_compile_workflow_payload_rejects_blank_picker_without_models() -> None:
    """Reject a required model picker when no local choices exist."""
    with pytest.raises(RuntimeError) as error_info:
        _compile_inputs(
            {
                "1": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": ""},
                    "_meta": {
                        "substitute": {
                            "cube_alias": "SDXL/Text to Image",
                            "node_name": "checkpoint",
                        }
                    },
                }
            },
            {
                "CheckpointLoaderSimple": {
                    "input": {"required": {"ckpt_name": [[], {}]}}
                }
            },
            sugar_script_text='use "cube" as "SDXL/Text to Image"',
        )

    message = str(error_info.value)
    assert "No local Comfy picker default is available" in message
    assert "cube_alias=SDXL/Text to Image" in message
    assert "node_name=checkpoint" in message


def test_compile_workflow_payload_rejects_blank_upscaler_without_models() -> None:
    """Reject an empty required upscaler picker at execution time."""
    with pytest.raises(RuntimeError) as error_info:
        _compile_inputs(
            {
                "1": {
                    "class_type": "UpscaleModelLoader",
                    "inputs": {"model_name": ""},
                    "_meta": {
                        "substitute": {
                            "cube_alias": "upscale",
                            "node_name": "upscale_model",
                        }
                    },
                }
            },
            {
                "UpscaleModelLoader": {
                    "input": {"required": {"model_name": ["COMBO", {"options": []}]}}
                }
            },
            sugar_script_text="use Upscale as upscale",
        )

    message = str(error_info.value)
    assert "No local Comfy picker default is available" in message
    assert "cube_alias=upscale" in message
    assert "node_name=upscale_model" in message
    assert "input=model_name" in message


def test_compile_workflow_payload_replaces_unavailable_combo_picker_default(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Treat an unavailable authored picker value as a local preference."""
    workflow_payload: dict[str, object] = {
        "1": {
            "class_type": "SeedVR2LoadDiTModel",
            "inputs": {"model": "missing.safetensors", "device": "cuda:0"},
            "_meta": {"substitute": {"cube_alias": "up", "node_name": "load_dit"}},
        }
    }
    service, _repository, _compiler = build_service(
        workflow_payload,
        node_definition_gateway=FakeNodeDefinitionGateway(
            {
                "SeedVR2LoadDiTModel": {
                    "input": {
                        "required": {
                            "model": [
                                "COMBO",
                                {
                                    "default": "seedvr2_default.safetensors",
                                    "options": ["seedvr2_default.safetensors"],
                                },
                            ],
                            "device": [
                                "COMBO",
                                {"default": "cuda:0", "options": ["cuda:0"]},
                            ],
                        }
                    }
                }
            }
        ),
    )

    with caplog.at_level(
        logging.DEBUG,
        logger="sugarsubstitute.application.recipes.picker_defaults",
    ):
        payload = service.compile_workflow_payload(
            sugar_script_text="use Cube as up",
            output_dir=Path("projects"),
        )

    node = cast(dict[str, Any], payload["1"])
    inputs = cast(dict[str, Any], node["inputs"])
    assert inputs["model"] == "seedvr2_default.safetensors"
    assert inputs["device"] == "cuda:0"
    assert "Replaced unavailable authored picker value" in caplog.text
