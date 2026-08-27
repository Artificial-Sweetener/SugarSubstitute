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

"""Wrapper-authored default contracts."""

from __future__ import annotations


from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.application.node_behavior import (
    FieldValueSource,
)
from tests.support.node_behavior import (
    cube_state,
)
from tests.application.node_behavior.service.support import (
    RequiredOnlyNodeDefinitionGateway,
)


def test_loaded_wrapper_preserves_authored_defaults_over_live_metadata() -> None:
    """Loaded wrapper fields should keep authored values when live defaults differ."""

    wrapper_id = "de2c84e5-02a8-4c50-831d-3c169dee4820"
    service = NodeBehaviorService(
        node_definition_gateway=RequiredOnlyNodeDefinitionGateway(
            {
                "VideoUpscaler": {
                    "input": {
                        "required": {
                            "color_correction": [
                                "COMBO",
                                {"default": "lab", "options": ["lab", "none"]},
                            ],
                            "input_noise_scale": [
                                "FLOAT",
                                {"default": 0.0, "min": 0.0, "max": 1.0},
                            ],
                            "encode_tiled": ["BOOLEAN", {"default": False}],
                        }
                    }
                }
            }
        )
    )
    cube = cube_state(
        nodes={"upscale_by_factor": {"class_type": wrapper_id, "inputs": {}}},
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
        subgraphs=[
            {
                "id": wrapper_id,
                "name": "Upscale by Factor",
                "inputNode": {"id": -10},
                "inputs": [
                    {
                        "name": "color_correction",
                        "label": "Color Correction",
                        "type": "COMBO",
                        "linkIds": [1],
                    },
                    {
                        "name": "input_noise_scale",
                        "label": "Input Noise Scale",
                        "type": "FLOAT",
                        "linkIds": [2],
                    },
                    {
                        "name": "encode_tiled",
                        "label": "Encode Tiled",
                        "type": "BOOLEAN",
                        "linkIds": [3],
                    },
                ],
                "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
                "links": [
                    {"id": 1, "origin_id": -10, "target_id": 20, "target_slot": 0},
                    {"id": 2, "origin_id": -10, "target_id": 20, "target_slot": 1},
                    {"id": 3, "origin_id": -10, "target_id": 20, "target_slot": 2},
                ],
                "nodes": [
                    {
                        "id": 20,
                        "type": "VideoUpscaler",
                        "inputs": [
                            {
                                "name": "color_correction",
                                "type": "COMBO",
                                "widget": {"name": "color_correction"},
                            },
                            {
                                "name": "input_noise_scale",
                                "type": "FLOAT",
                                "widget": {"name": "input_noise_scale"},
                            },
                            {
                                "name": "encode_tiled",
                                "type": "BOOLEAN",
                                "widget": {"name": "encode_tiled"},
                            },
                        ],
                        "widgets_values": ["none", 0.025, True],
                    }
                ],
            }
        ],
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    specs = snapshot.field_specs_by_alias["A"]["upscale_by_factor"]
    assert specs["color_correction"].value == "none"
    assert specs["color_correction"].value_source == FieldValueSource.AUTHORED_DEFAULT
    assert specs["input_noise_scale"].value == 0.025
    assert specs["input_noise_scale"].value_source == FieldValueSource.AUTHORED_DEFAULT
    assert specs["encode_tiled"].value is True
    assert specs["encode_tiled"].value_source == FieldValueSource.AUTHORED_DEFAULT


def test_loaded_wrapper_preserves_authored_combo_default_outside_live_options() -> None:
    """Loaded wrapper combo defaults should not be replaced by live option fallbacks."""

    wrapper_id = "de2c84e5-02a8-4c50-831d-3c169dee4820"
    service = NodeBehaviorService(
        node_definition_gateway=RequiredOnlyNodeDefinitionGateway(
            {
                "VideoUpscaler": {
                    "input": {
                        "required": {
                            "color_correction": [
                                "COMBO",
                                {"default": "lab", "options": ["lab"]},
                            ],
                        }
                    }
                }
            }
        )
    )
    cube = cube_state(
        nodes={"upscale_by_factor": {"class_type": wrapper_id, "inputs": {}}},
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
        subgraphs=[
            {
                "id": wrapper_id,
                "name": "Upscale by Factor",
                "inputNode": {"id": -10},
                "inputs": [
                    {
                        "name": "color_correction",
                        "label": "Color Correction",
                        "type": "COMBO",
                        "linkIds": [1],
                    },
                ],
                "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
                "links": [
                    {"id": 1, "origin_id": -10, "target_id": 20, "target_slot": 0},
                ],
                "nodes": [
                    {
                        "id": 20,
                        "type": "VideoUpscaler",
                        "inputs": [
                            {
                                "name": "color_correction",
                                "type": "COMBO",
                                "widget": {"name": "color_correction"},
                            },
                        ],
                        "widgets_values": ["none"],
                    }
                ],
            }
        ],
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["upscale_by_factor"]["color_correction"]
    assert spec.value == "none"
    assert spec.value_source == FieldValueSource.AUTHORED_DEFAULT
    assert cube.buffer["nodes"]["upscale_by_factor"]["inputs"] == {}
