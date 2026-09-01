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

"""Verify cube surface controls define reusable model onboarding categories."""

from __future__ import annotations

from substitute.application.model_discovery import cube_model_capabilities
from substitute.domain.cubes import CanonicalCubeDocument
from sugarsubstitute_shared.model_discovery import ModelCategory


def test_capabilities_include_only_supported_exposed_model_picker_fields() -> None:
    """Hidden nodes and unsupported model kinds should not become installer interests."""

    document = CanonicalCubeDocument(
        cube_id="image-cube",
        version="1.0.0",
        description="",
        metadata={},
        implementation={
            "nodes": {
                "hidden": {
                    "class_type": "ControlNetLoader",
                    "inputs": {"control_net_name": "hidden.safetensors"},
                }
            }
        },
        surface={
            "default_flavor_id": "default",
            "controls": [
                {
                    "control_id": "checkpoint",
                    "symbol": "loader",
                    "input_name": "ckpt_name",
                    "label": "Checkpoint",
                    "class_type": "CheckpointLoaderSimple",
                    "value_type": "string",
                },
                {
                    "control_id": "lora",
                    "symbol": "lora",
                    "input_name": "lora_name",
                    "label": "LoRA",
                    "class_type": "LoraLoader",
                    "value_type": "string",
                },
                {
                    "control_id": "unsupported",
                    "symbol": "embedding",
                    "input_name": "embedding_name",
                    "label": "Embedding",
                    "class_type": "EmbeddingLoader",
                    "value_type": "string",
                },
            ],
        },
        flavors={"authored": []},
    )

    capabilities = cube_model_capabilities((document,))

    assert capabilities[0].cube_id == "image-cube"
    assert capabilities[0].categories == frozenset(
        {ModelCategory.CHECKPOINTS, ModelCategory.LORAS}
    )
