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

"""Contract tests for the application node-behavior service."""

from __future__ import annotations

import logging
from typing import Mapping

import pytest

from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.application.node_behavior import (
    ActivationDefault,
    CardMode,
    CollapseMode,
    EnabledSwitchPolicy,
    FieldBehaviorPatch,
    FieldPresentation,
    FieldValueSource,
    LiveNodeDefinitionError,
    ModelBackedNodeDetector,
    NodeBehaviorPatch,
    NodeBehaviorRuntimeState,
    PackageBehaviorPatch,
)
from substitute.application.model_metadata import ModelCatalogItem
from substitute.application.node_behavior.list_value_resolver import (
    extract_live_list_options,
)
from tests.node_behavior_test_helpers import (
    DummyNodeDefinitionGateway,
    build_behavior_snapshot,
    cube_state,
)


UUID_WRAPPER = "644694cf-354b-4cc8-8a67-a78145a8180e"
UUID_NESTED_WRAPPER = "8f6c43da-07af-4666-9e9a-0b4c7f83bdad"


class RecordingNodeDefinitionGateway(DummyNodeDefinitionGateway):
    """Record requested class types while returning deterministic definitions."""

    def __init__(
        self, definitions: Mapping[str, Mapping[str, object]] | None = None
    ) -> None:
        """Initialize the recording gateway with optional definitions."""

        super().__init__(definitions)
        self.requests: list[str] = []

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Record the requested class before returning a test definition."""

        self.requests.append(node_class)
        return super().get_node_definition(node_class)


class RequiredOnlyNodeDefinitionGateway(DummyNodeDefinitionGateway):
    """Return definitions only from the required lookup path."""

    def __init__(
        self, definitions: Mapping[str, Mapping[str, object]] | None = None
    ) -> None:
        """Initialize the gateway with optional required definitions."""

        super().__init__(definitions)
        self.optional_requests: list[str] = []
        self.required_requests: list[str] = []

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Record optional lookups and simulate an empty cache miss."""

        self.optional_requests.append(node_class)
        return {}

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Record required lookups and return the configured definition."""

        self.required_requests.append(node_class)
        return super().get_required_node_definition(node_class)


def _wrapper_subgraphs() -> list[dict[str, object]]:
    """Return one wrapper subgraph plus an internal body node for behavior tests."""

    return [
        {
            "id": UUID_WRAPPER,
            "name": "Detailer",
            "inputs": [
                {"name": "image", "label": "Image", "type": "IMAGE", "linkIds": [1]},
                {"name": "steps", "label": "Steps", "type": "INT", "linkIds": [2]},
                {"name": "cfg", "label": "CFG", "type": "FLOAT", "linkIds": [3]},
                {
                    "name": "sampler_name",
                    "label": "Sampler",
                    "type": "COMBO",
                    "linkIds": [4],
                },
                {
                    "name": "denoise",
                    "label": "Denoise",
                    "type": "FLOAT",
                    "linkIds": [5],
                },
            ],
            "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
            "links": [
                {"id": 1, "origin_id": -10, "target_id": 1470, "target_slot": 0},
                {"id": 2, "origin_id": -10, "target_id": 1470, "target_slot": 1},
                {"id": 3, "origin_id": -10, "target_id": 1470, "target_slot": 2},
                {"id": 4, "origin_id": -10, "target_id": 1470, "target_slot": 3},
                {"id": 5, "origin_id": -10, "target_id": 1470, "target_slot": 4},
            ],
            "nodes": [
                {
                    "id": 1470,
                    "type": "DetailerForEach",
                    "inputs": [
                        {"name": "image", "type": "IMAGE"},
                        {"name": "steps", "type": "INT", "widget": {"name": "steps"}},
                        {"name": "cfg", "type": "FLOAT", "widget": {"name": "cfg"}},
                        {
                            "name": "sampler_name",
                            "type": "COMBO",
                            "widget": {"name": "sampler_name"},
                        },
                        {
                            "name": "denoise",
                            "type": "FLOAT",
                            "widget": {"name": "denoise"},
                        },
                    ],
                    "widgets_values": [12, 7.0, "euler_ancestral", 0.65],
                }
            ],
        }
    ]


def _wrapper_definitions() -> dict[str, object]:
    """Return hidden body-node definitions for wrapper metadata enrichment tests."""

    return {
        "DetailerForEach": {
            "input": {
                "required": {
                    "denoise": [
                        "FLOAT",
                        {
                            "default": 0.5,
                            "min": 0.0001,
                            "max": 1.0,
                            "step": 0.01,
                        },
                    ]
                }
            }
        }
    }


def _wrapper_live_definitions() -> dict[str, Mapping[str, object]]:
    """Return live body-node definitions for wrapper behavior tests."""

    return {
        "ImageSource": {"input": {"required": {"path": ["STRING", {}]}}},
        "DetailerForEach": {
            "input": {
                "required": {
                    "image": ["IMAGE", {}],
                    "steps": ["INT", {"default": 12, "min": 1, "max": 80, "step": 1}],
                    "cfg": [
                        "FLOAT",
                        {"default": 7.0, "min": 0.0, "max": 30.0, "step": 0.1},
                    ],
                    "sampler_name": [
                        ["euler", "euler_ancestral"],
                        {"default": "euler_ancestral"},
                    ],
                    "denoise": [
                        "FLOAT",
                        {
                            "default": 0.65,
                            "min": 0.0001,
                            "max": 1.0,
                            "step": 0.01,
                        },
                    ],
                }
            }
        },
    }


def _wrapper_nodes() -> dict[str, object]:
    """Return surface nodes containing one UUID wrapper node."""

    return {
        "source": {"class_type": "ImageSource", "inputs": {"path": "a.png"}},
        "detailer": {
            "class_type": UUID_WRAPPER,
            "inputs": {"image": ["source", 0], "steps": 12},
        },
    }


def _nested_wrapper_subgraphs() -> list[dict[str, object]]:
    """Return parent and nested wrapper subgraphs for behavior projection tests."""

    return [
        {
            "id": UUID_WRAPPER,
            "name": "Detailer",
            "inputNode": {"id": -10},
            "inputs": [
                {
                    "name": "c",
                    "label": "Scale Factor",
                    "type": "INT,FLOAT,IMAGE,LATENT",
                    "linkIds": [1049],
                }
            ],
            "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
            "links": [[1049, -10, 0, 1633, 0, "FLOAT"]],
            "nodes": [
                {
                    "id": 1633,
                    "type": UUID_NESTED_WRAPPER,
                    "inputs": [
                        {
                            "name": "value",
                            "type": "FLOAT",
                            "widget": {"name": "value"},
                            "link": 1049,
                        }
                    ],
                    "widgets_values": [],
                }
            ],
        },
        {
            "id": UUID_NESTED_WRAPPER,
            "name": "Scale Masked Area by Factor",
            "inputNode": {"id": -10},
            "inputs": [
                {"name": "value", "label": "Value", "type": "FLOAT", "linkIds": [1048]}
            ],
            "outputs": [{"name": "SEGS", "label": "Segs", "type": "SEGS"}],
            "links": [[1048, -10, 0, 1634, 0, "FLOAT"]],
            "nodes": [
                {
                    "id": 1634,
                    "type": "PrimitiveFloat",
                    "inputs": [
                        {
                            "name": "value",
                            "type": "FLOAT",
                            "widget": {"name": "value"},
                            "link": 1048,
                        }
                    ],
                    "widgets_values": [1.5],
                }
            ],
        },
    ]


def _nested_wrapper_definitions() -> dict[str, object]:
    """Return primitive body definitions used by nested wrapper tests."""

    return {
        "PrimitiveFloat": {
            "input": {
                "required": {
                    "value": [
                        "FLOAT",
                        {"default": 1.0, "min": 0.25, "max": 3.0, "step": 0.05},
                    ]
                }
            }
        }
    }


def _nested_wrapper_live_definitions() -> dict[str, Mapping[str, object]]:
    """Return live primitive body definitions used by nested wrapper tests."""

    return {
        "PrimitiveFloat": {
            "input": {
                "required": {
                    "value": [
                        "FLOAT",
                        {"default": 1.0, "min": 0.25, "max": 3.0, "step": 0.05},
                    ]
                }
            }
        }
    }


def test_behavior_snapshot_uses_subgraph_wrapper_virtual_definition() -> None:
    """Wrapper nodes should resolve fields from public subgraph interfaces."""

    cube = cube_state(
        nodes=_wrapper_nodes(),
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_wrapper_live_definitions(),
    )

    detailer_specs = snapshot.field_specs_by_alias["A"]["detailer"]
    assert list(detailer_specs) == ["image", "steps", "cfg", "sampler_name", "denoise"]
    assert detailer_specs["image"].field_type == "IMAGE"
    assert detailer_specs["steps"].field_type == "INT"
    assert detailer_specs["cfg"].field_type == "FLOAT"
    assert detailer_specs["sampler_name"].field_type == "LIST"
    assert detailer_specs["denoise"].field_type == "FLOAT"
    assert detailer_specs["denoise"].constraints == {
        "min": 0.0001,
        "max": 1.0,
        "step": 0.01,
    }
    assert "tooltip" not in detailer_specs["denoise"].meta_info
    assert detailer_specs["steps"].meta_info["subgraph_wrapper"] is True
    assert detailer_specs["steps"].meta_info["subgraph_id"] == UUID_WRAPPER


def test_behavior_snapshot_does_not_project_subgraph_body_nodes() -> None:
    """Subgraph body nodes should not enter behavior maps or field specs."""

    cube = cube_state(
        nodes=_wrapper_nodes(),
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_wrapper_live_definitions(),
    )

    assert list(snapshot.resolved_nodes_by_alias["A"]) == ["source", "detailer"]
    assert "DetailerForEach" not in snapshot.resolved_nodes_by_alias["A"]
    assert "DetailerForEach" not in snapshot.field_specs_by_alias["A"]


def test_behavior_snapshot_preserves_prompts_first_wired_node_order() -> None:
    """Behavior snapshot maps should expose the shared node-card order."""

    cube = cube_state(
        nodes={
            "ksampler": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["checkpoint", 0],
                    "positive": ["text_b", 0],
                    "negative": ["text_a", 0],
                    "latent": ["latent_source", 0],
                },
            },
            "latent_source": {
                "class_type": "CustomLatentProducer",
                "inputs": {"model": ["checkpoint", 0]},
            },
            "checkpoint": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            },
            "text_a": {"class_type": "CLIPTextEncode", "inputs": {}},
            "text_b": {"class_type": "CLIPTextEncode", "inputs": {}},
        },
    )
    cube.buffer["layout"] = {
        "nodes": {
            "text_a": {"title": "Negative Prompt"},
            "text_b": {"title": "Positive Prompt"},
        }
    }

    snapshot = build_behavior_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert list(snapshot.resolved_nodes_by_alias["A"]) == [
        "text_b",
        "text_a",
        "checkpoint",
        "latent_source",
        "ksampler",
    ]


def test_behavior_snapshot_does_not_query_live_gateway_for_uuid_wrapper() -> None:
    """UUID wrappers should resolve locally instead of querying live Comfy metadata."""

    cube = cube_state(
        nodes=_wrapper_nodes(),
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )
    gateway = RecordingNodeDefinitionGateway(_wrapper_live_definitions())
    service = NodeBehaviorService(node_definition_gateway=gateway)

    service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert UUID_WRAPPER not in gateway.requests
    assert "ImageSource" in gateway.requests


def test_wrapper_display_name_is_available_for_card_behavior() -> None:
    """Resolved wrapper behavior should expose the public subgraph display name."""

    cube = cube_state(
        nodes=_wrapper_nodes(),
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_wrapper_live_definitions(),
    )

    assert snapshot.resolved_nodes_by_alias["A"]["detailer"].display_name == "Detailer"


def test_normal_node_raw_title_does_not_override_card_display_label() -> None:
    """Raw Comfy titles should not bypass normal node-card title formatting."""

    cube = cube_state(
        nodes={
            "mahiro CFG": {
                "class_type": "MahiroCFG",
                "inputs": {},
                "_meta": {"title": "mahiro CFG"},
            },
            "vectorscopeCC": {
                "class_type": "VectorscopeCC",
                "inputs": {},
                "_meta": {"title": "vectorscopeCC"},
            },
        },
        definitions={
            "MahiroCFG": {"input": {"required": {}}},
            "VectorscopeCC": {"input": {"required": {}}},
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_wrapper_live_definitions(),
    )

    assert snapshot.resolved_nodes_by_alias["A"]["mahiro CFG"].display_name is None
    assert snapshot.resolved_nodes_by_alias["A"]["vectorscopeCC"].display_name is None


def test_wrapper_surface_node_gets_title_control_when_all_inputs_are_linked() -> None:
    """Wrapper nodes should render public default controls from interface links."""

    cube = cube_state(
        nodes={
            "source": {"class_type": "ImageSource", "inputs": {"path": "a.png"}},
            "detailer": {
                "class_type": UUID_WRAPPER,
                "inputs": {"image": ["source", 0]},
            },
        },
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_wrapper_live_definitions(),
    )

    detailer_specs = snapshot.field_specs_by_alias["A"]["detailer"]
    detailer_decision = snapshot.card_decisions_by_alias["A"]["detailer"]
    detailer_behavior = snapshot.resolved_nodes_by_alias["A"]["detailer"]
    assert list(detailer_specs) == ["image", "steps", "cfg", "sampler_name", "denoise"]
    assert detailer_specs["steps"].value == 12
    assert detailer_specs["steps"].raw_value is None
    assert detailer_specs["steps"].value_source == FieldValueSource.AUTHORED_DEFAULT
    assert detailer_specs["cfg"].value == 7.0
    assert detailer_specs["sampler_name"].value == "euler_ancestral"
    assert detailer_specs["denoise"].value == 0.65
    assert detailer_specs["denoise"].constraints["min"] == 0.0001
    assert detailer_decision.visible is True
    assert detailer_decision.show_enabled_switch is False
    assert detailer_behavior.card.enabled_switch_policy == EnabledSwitchPolicy.NEVER
    assert detailer_behavior.card.icon_name == "application"


def test_wrapper_surface_value_overrides_linked_body_default() -> None:
    """Surface wrapper inputs should override extracted hidden body widget defaults."""

    cube = cube_state(
        nodes={
            "source": {"class_type": "ImageSource", "inputs": {"path": "a.png"}},
            "detailer": {
                "class_type": UUID_WRAPPER,
                "inputs": {"image": ["source", 0], "denoise": 0.8},
            },
        },
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_wrapper_live_definitions(),
    )

    denoise = snapshot.field_specs_by_alias["A"]["detailer"]["denoise"]
    assert denoise.value == 0.8
    assert denoise.raw_value == 0.8
    assert denoise.value_source == FieldValueSource.EXPLICIT


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


def test_loaded_cube_missing_numeric_input_uses_live_default() -> None:
    """Loaded cubes should render missing numeric values from live defaults."""

    cube = cube_state(
        nodes={"sampler": {"class_type": "Sampler", "inputs": {}}},
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "Sampler": {
                    "input": {
                        "required": {
                            "steps": ["INT", {"default": 20, "min": 1, "max": 150}]
                        }
                    }
                }
            }
        )
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["sampler"]["steps"]
    assert spec.value == 20
    assert spec.value_source == FieldValueSource.LIVE_DEFAULT


def test_loaded_cube_missing_combo_uses_live_default() -> None:
    """Loaded cubes should render missing choices from live defaults."""

    cube = cube_state(
        nodes={"sampler": {"class_type": "Sampler", "inputs": {}}},
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "Sampler": {
                    "input": {
                        "required": {
                            "sampler_name": [
                                ["euler", "ddim"],
                                {"default": "ddim"},
                            ],
                        }
                    }
                }
            }
        )
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["sampler"]["sampler_name"]
    assert spec.value == "ddim"
    assert spec.value_source == FieldValueSource.LIVE_DEFAULT


def test_loaded_cube_missing_combo_without_default_uses_first_live_option() -> None:
    """Loaded cubes should render missing choices from the first live option."""

    cube = cube_state(
        nodes={"sampler": {"class_type": "Sampler", "inputs": {}}},
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "Sampler": {
                    "input": {
                        "required": {
                            "sampler_name": [["euler", "ddim"], {}],
                        }
                    }
                }
            }
        )
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["sampler"]["sampler_name"]
    assert spec.value == "euler"
    assert spec.value_source == FieldValueSource.FIRST_OPTION


def test_loaded_cube_blank_combo_uses_live_default_without_dirtying() -> None:
    """Loaded cube blank choice literals should render live defaults without mutation."""

    cube = cube_state(
        nodes={"loader": {"class_type": "ModelLoader", "inputs": {"model": ""}}},
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "ModelLoader": {
                    "input": {
                        "required": {
                            "model": [
                                ["authored.safetensors", "live-default.safetensors"],
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
    assert spec.value == "live-default.safetensors"
    assert spec.value_source == FieldValueSource.LIVE_DEFAULT
    assert cube.buffer["nodes"]["loader"]["inputs"]["model"] == ""
    assert cube.dirty is False


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


def test_wrapper_surface_missing_live_body_definition_raises() -> None:
    """Wrapper body metadata must come from live Comfy definitions."""

    cube = cube_state(
        nodes=_wrapper_nodes(),
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )

    with pytest.raises(LiveNodeDefinitionError) as error_info:
        build_behavior_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert error_info.value.operation == "resolve wrapper body node metadata"
    assert error_info.value.missing_definitions[0].class_type == "DetailerForEach"
    assert error_info.value.missing_definitions[0].cube_aliases == ("A",)
    assert error_info.value.missing_definitions[0].node_names == ("detailer",)


def test_wrapper_body_metadata_uses_required_definition_lookup() -> None:
    """Wrapper body metadata should synchronously require live Comfy definitions."""

    cube = cube_state(
        nodes=_wrapper_nodes(),
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )
    gateway = RequiredOnlyNodeDefinitionGateway(_wrapper_live_definitions())
    service = NodeBehaviorService(node_definition_gateway=gateway)

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert snapshot.field_specs_by_alias["A"]["detailer"]["denoise"].field_type == (
        "FLOAT"
    )
    assert "DetailerForEach" in gateway.required_requests
    assert "DetailerForEach" not in gateway.optional_requests


def test_wrapper_nested_public_input_is_exposed_from_nested_wrapper_default() -> None:
    """Parent wrapper fields routed through nested wrappers should still render."""

    cube = cube_state(
        nodes={
            "detailer": {
                "class_type": UUID_WRAPPER,
                "inputs": {},
            },
        },
        definitions=_nested_wrapper_definitions(),
        subgraphs=_nested_wrapper_subgraphs(),
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_nested_wrapper_live_definitions(),
    )

    detailer_specs = snapshot.field_specs_by_alias["A"]["detailer"]
    assert list(detailer_specs) == ["c"]
    scale_factor = detailer_specs["c"]
    assert scale_factor.field_type == "FLOAT"
    assert scale_factor.value == 1.5
    assert scale_factor.value_source == FieldValueSource.AUTHORED_DEFAULT
    assert scale_factor.constraints == {"min": 0.25, "max": 3.0, "step": 0.05}
    assert scale_factor.meta_info["label"] == "Scale Factor"
    assert scale_factor.meta_info["interface_type"] == "INT,FLOAT,IMAGE,LATENT"
    assert UUID_NESTED_WRAPPER not in snapshot.field_specs_by_alias["A"]
    assert "PrimitiveFloat" not in snapshot.field_specs_by_alias["A"]


def test_wrapper_public_constraints_override_body_primitive_constraints() -> None:
    """Wrapper fields should preserve authored public bounds over body primitive bounds."""

    cube = cube_state(
        nodes={
            "upscale_by_factor": {
                "class_type": UUID_WRAPPER,
                "inputs": {},
            },
        },
        definitions=_nested_wrapper_definitions(),
        subgraphs=_nested_wrapper_subgraphs(),
    )
    cube.buffer["definitions"] = {
        "PrimitiveFloat": {
            "input": {
                "required": {
                    "value": [
                        "FLOAT",
                        {
                            "default": 1.0,
                            "min": -9_223_372_036_854_775_807,
                            "max": 9_223_372_036_854_775_807,
                            "step": 0.1,
                        },
                    ]
                }
            }
        }
    }
    subgraphs = cube.buffer["subgraphs"]
    assert isinstance(subgraphs, list)
    wrapper = subgraphs[0]
    assert isinstance(wrapper, dict)
    inputs = wrapper["inputs"]
    assert isinstance(inputs, list)
    public_input = inputs[0]
    assert isinstance(public_input, dict)
    public_input["min"] = 0.1
    public_input["max"] = 10.0

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "PrimitiveFloat": {
                "input": {
                    "required": {
                        "value": [
                            "FLOAT",
                            {
                                "default": 1.0,
                                "min": -9_223_372_036_854_775_807,
                                "max": 9_223_372_036_854_775_807,
                                "step": 0.1,
                            },
                        ]
                    }
                }
            }
        },
    )

    scale_factor = snapshot.field_specs_by_alias["A"]["upscale_by_factor"]["c"]
    assert scale_factor.meta_info["label"] == "Scale Factor"
    assert scale_factor.constraints == {"min": 0.1, "max": 10.0, "step": 0.1}


def test_build_snapshot_exposes_all_editor_behavior_buckets() -> None:
    """Service snapshots should include resolved nodes, card decisions, hidden keys, and reveal entries."""

    cubes = {
        "A": cube_state(
            nodes={
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {
                        "seed": 7,
                        "sampler_name": "euler",
                        "scheduler": "karras",
                    },
                }
            },
            definitions={
                "KSampler": {
                    "input": {
                        "required": {
                            "seed": ["INT", {"min": 0, "max": 999999, "step": 1}],
                            "sampler_name": [["euler", "heun"], {}],
                            "scheduler": [["karras", "normal"], {}],
                        }
                    },
                }
            },
        ),
        "B": cube_state(
            nodes={
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "model-b"},
                }
            }
        ),
    }

    snapshot = build_behavior_snapshot(
        cube_states=cubes,
        stack_order=["A", "B"],
        definitions_by_class={
            "KSampler": {
                "input": {
                    "required": {
                        "seed": ["INT", {"min": 0, "max": 999999, "step": 1}],
                        "sampler_name": [["euler", "heun"], {}],
                        "scheduler": [["karras", "normal"], {}],
                    }
                },
            }
        },
        workflow_overrides={"seed": {"value": 1}},
    )

    assert "A" in snapshot.resolved_nodes_by_alias
    assert "A" in snapshot.field_specs_by_alias
    assert "A" in snapshot.card_decisions_by_alias
    assert "A" in snapshot.hidden_field_keys_by_alias
    assert "B" in snapshot.reveal_entries_by_alias
    assert "ksampler" in snapshot.resolved_nodes_by_alias["A"]
    assert snapshot.field_specs_by_alias["A"]["ksampler"]["seed"].field_type == "INT"
    assert ("A", "ksampler", "seed") in snapshot.hidden_field_keys_by_alias["A"]


def test_build_snapshot_exposes_comfy_tooltip_metadata() -> None:
    """Comfy node descriptions and field tooltips should enter render contracts."""

    cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"steps": 20},
            }
        }
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "KSampler": {
                "description": "Samples an image from latent noise.",
                "input": {
                    "required": {
                        "steps": [
                            "INT",
                            {"tooltip": "Number of denoise steps."},
                        ]
                    }
                },
            }
        },
    )

    resolved = snapshot.resolved_nodes_by_alias["A"]["sampler"]
    field_spec = snapshot.field_specs_by_alias["A"]["sampler"]["steps"]
    assert resolved.card.tooltip == "Samples an image from latent noise."
    assert field_spec.meta_info["tooltip"] == "Number of denoise steps."


@pytest.mark.parametrize("description", ["", "   ", {"text": "not renderable"}])
def test_build_snapshot_ignores_blank_or_invalid_comfy_node_tooltips(
    description: object,
) -> None:
    """Blank and non-string node descriptions should not become card tooltips."""

    cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"steps": 20},
            }
        }
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "KSampler": {
                "description": description,
                "input": {"required": {"steps": ["INT", {}]}},
            }
        },
    )

    assert snapshot.resolved_nodes_by_alias["A"]["sampler"].card.tooltip is None


def test_build_snapshot_ignores_cube_authored_tooltips_when_live_missing() -> None:
    """Cube-authored node and field tooltips should not render without live metadata."""

    cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"steps": 20},
            }
        },
        definitions={
            "KSampler": {
                "description": "Cube-authored node tooltip.",
                "input": {
                    "required": {
                        "steps": ["INT", {"tooltip": "Cube-authored field tooltip."}]
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(cube_states={"A": cube}, stack_order=["A"])

    resolved = snapshot.resolved_nodes_by_alias["A"]["sampler"]
    field_spec = snapshot.field_specs_by_alias["A"]["sampler"]["steps"]
    assert resolved.card.tooltip is None
    assert "tooltip" not in field_spec.meta_info


def test_build_snapshot_orders_fields_from_definition_before_persisted_extras() -> None:
    """Sorted persisted inputs should not override cube definition field order."""

    cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "OrderedSampler",
                "inputs": {
                    "height": 768,
                    "prompt": "quality",
                    "seed": 123,
                    "unknown_extra": "kept",
                    "width": 512,
                },
            }
        },
        definitions={
            "OrderedSampler": {
                "input": {
                    "required": {
                        "prompt": ["STRING", {}],
                        "width": ["INT", {}],
                        "height": ["INT", {}],
                    },
                    "optional": {
                        "seed": ["INT", {}],
                    },
                }
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "OrderedSampler": {
                "input": {
                    "required": {
                        "prompt": ["STRING", {}],
                        "width": ["INT", {}],
                        "height": ["INT", {}],
                    },
                    "optional": {
                        "seed": ["INT", {}],
                    },
                }
            }
        },
    )

    assert list(snapshot.field_specs_by_alias["A"]["sampler"]) == [
        "prompt",
        "width",
        "height",
        "seed",
        "unknown_extra",
    ]


def test_prompt_card_icons_distinguish_positive_and_negative_prompts() -> None:
    """Positive prompt keeps edit while negative prompt uses the eraser icon."""

    cube = cube_state(
        nodes={
            "positive_prompt": {
                "class_type": "CLIPTextEncode",
                "inputs": {"prompt_template": "quality"},
            },
            "negative_prompt": {
                "class_type": "CLIPTextEncode",
                "inputs": {"prompt_template": "blurry"},
            },
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )

    assert (
        snapshot.resolved_nodes_by_alias["A"]["positive_prompt"].card.icon_name
        == "edit"
    )
    assert (
        snapshot.resolved_nodes_by_alias["A"]["negative_prompt"].card.icon_name
        == "eraser"
    )


def test_inferred_negative_prompt_card_uses_eraser_icon() -> None:
    """Titled custom negative prompt cards should use the eraser icon."""

    cube = cube_state(
        nodes={
            "node_18": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "blurry"},
                "_meta": {"title": "Negative Prompt"},
            },
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "CLIPTextEncode": {
                "input": {
                    "required": {
                        "text": ["STRING", {"multiline": True}],
                    }
                }
            }
        },
    )

    assert snapshot.resolved_nodes_by_alias["A"]["node_18"].card.icon_name == "eraser"


def test_simple_syrup_schedule_node_is_hidden_infrastructure() -> None:
    """SimpleSyrup schedule nodes should not expose editor card UI."""

    node_class = "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
    cube = cube_state(
        nodes={
            "schedule": {
                "class_type": node_class,
                "inputs": {
                    "positive_prompt": "quality",
                    "negative_prompt": "blurry",
                    "encode_style": "standard",
                },
            },
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            node_class: {
                "input": {
                    "required": {
                        "positive_prompt": ["STRING", {"multiline": True}],
                        "negative_prompt": ["STRING", {"multiline": True}],
                        "encode_style": ["STRING", {}],
                    }
                }
            }
        },
    )

    fields = snapshot.field_specs_by_alias["A"]["schedule"]
    positive_behavior = fields["positive_prompt"].field_behavior
    negative_behavior = fields["negative_prompt"].field_behavior
    style_behavior = fields["encode_style"].field_behavior

    card = snapshot.resolved_nodes_by_alias["A"]["schedule"].card
    decision = snapshot.card_decisions_by_alias["A"]["schedule"]
    assert card.card_mode is CardMode.STANDARD
    assert card.collapse_mode is CollapseMode.AUTO
    assert card.activation_default is ActivationDefault.ENABLED
    assert card.hidden is True
    assert card.icon_name is None
    assert decision.visible is False
    assert decision.enabled is True
    assert decision.revealable is False
    assert decision.show_enabled_switch is False
    assert positive_behavior.presentation is FieldPresentation.STANDARD
    assert positive_behavior.prompt is None
    assert negative_behavior.presentation is FieldPresentation.STANDARD
    assert negative_behavior.prompt is None
    assert style_behavior.presentation is FieldPresentation.STANDARD


def test_build_snapshot_keeps_definition_resolution_details_out_of_info_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Normal behavior snapshots should log summaries without per-node detail spam."""

    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {"KSampler": {"input": {"required": {"seed": ["INT", {}]}}}}
        )
    )
    cubes = {
        "A": cube_state(
            nodes={
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {"seed": 7},
                }
            },
            definitions={
                "KSampler": {"input": {"required": {"seed": ["INT", {}]}}},
            },
        )
    }

    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.application.node_behavior.behavior_service",
    )
    service.build_snapshot(cube_states=cubes, stack_order=["A"])

    assert "Built editor behavior snapshot" in caplog.text
    assert "Resolved node definition from live and cube metadata" not in caplog.text
    assert "Resolved empty node definition" not in caplog.text


def test_build_snapshot_reveal_entries_track_revealable_hidden_nodes() -> None:
    """Reveal menu entries should come from the same node display decisions."""

    cubes = {
        "A": cube_state(
            nodes={"vae": {"class_type": "VAELoader", "inputs": {}, "mode": 4}},
        ),
        "B": cube_state(
            nodes={"ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {}}},
        ),
        "C": cube_state(
            nodes={
                "ckpt": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "later"},
                    "mode": 4,
                }
            },
        ),
    }

    snapshot = build_behavior_snapshot(cube_states=cubes, stack_order=["A", "B", "C"])

    assert [entry.node_name for entry in snapshot.reveal_entries_by_alias["A"]] == [
        "vae"
    ]
    assert snapshot.reveal_entries_by_alias["B"] == []
    assert [entry.node_name for entry in snapshot.reveal_entries_by_alias["C"]] == [
        "ckpt"
    ]
    assert snapshot.reveal_entries_by_alias["A"][0].checked is False
    assert snapshot.reveal_entries_by_alias["C"][0].checked is False


def test_runtime_state_is_created_and_reused_on_cube_state() -> None:
    """Runtime state helper should store one mutable runtime bucket on the cube state."""

    cube = cube_state()

    first = NodeBehaviorRuntimeState()
    cube.ui["node_behavior_runtime"] = first

    from substitute.application.node_behavior import NodeBehaviorService
    from tests.node_behavior_test_helpers import DummyNodeDefinitionGateway

    service = NodeBehaviorService(node_definition_gateway=DummyNodeDefinitionGateway())
    second = service.ensure_runtime_state(cube)

    assert second is first


def test_set_node_activation_override_writes_explicit_override_and_dirty_flag() -> None:
    """Activation commands should persist only explicit user intent."""

    from substitute.application.node_behavior import NodeBehaviorService
    from tests.node_behavior_test_helpers import DummyNodeDefinitionGateway

    cube = cube_state(
        nodes={"vae": {"class_type": "VAELoader", "inputs": {}}},
    )
    service = NodeBehaviorService(node_definition_gateway=DummyNodeDefinitionGateway())

    service.set_node_activation_override(cube, "vae", True)
    assert cube.buffer["nodes"]["vae"]["enabled"] is True
    assert cube.dirty is True

    cube.dirty = False
    service.set_node_activation_override(cube, "vae", None)
    assert "enabled" not in cube.buffer["nodes"]["vae"]
    assert cube.dirty is True


def test_set_node_visibility_override_writes_reveal_state_and_dirty_flag() -> None:
    """Reveal commands should persist editor visibility separately from activation."""

    from substitute.application.node_behavior import NodeBehaviorService
    from tests.node_behavior_test_helpers import DummyNodeDefinitionGateway

    cube = cube_state(
        nodes={"vae": {"class_type": "VAELoader", "inputs": {}}},
    )
    service = NodeBehaviorService(node_definition_gateway=DummyNodeDefinitionGateway())

    service.set_node_visibility_override(cube, "vae", True)
    assert cube.buffer["nodes"]["vae"]["revealed"] is True
    assert cube.dirty is True

    cube.dirty = False
    service.set_node_visibility_override(cube, "vae", True)
    assert cube.dirty is False

    service.set_node_visibility_override(cube, "vae", None)
    assert "revealed" not in cube.buffer["nodes"]["vae"]
    assert cube.dirty is True


def test_activation_and_reveal_overrides_can_coexist_independently() -> None:
    """Disabled-but-revealed bypass-authored nodes should be representable."""

    cube = cube_state(
        nodes={
            "vae": {
                "class_type": "VAELoader",
                "inputs": {},
                "mode": 4,
                "enabled": False,
                "revealed": True,
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )
    decision = snapshot.card_decisions_by_alias["A"]["vae"]

    assert decision.visible is True
    assert decision.enabled is False
    assert decision.explicit_override is False
    assert decision.explicit_revealed is True


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


def test_build_snapshot_preserves_asset_fields_outside_comfy_live_options() -> None:
    """Asset fields are Substitute-owned and must not canonicalize to Comfy options."""

    selected_image = "E:/images/selected.png"
    selected_mask = "E:/projects/Recipe/masks/selected_mask.png"
    cube = cube_state(
        nodes={
            "load_image": {
                "class_type": "LoadImage",
                "inputs": {"image": selected_image},
            },
            "load_image_as_mask": {
                "class_type": "LoadImageMask",
                "inputs": {"image": selected_mask},
            },
        },
    )
    snapshot = build_behavior_snapshot(
        cube_states={"Inpaint": cube},
        stack_order=["Inpaint"],
        definitions_by_class={
            "LoadImage": {
                "input": {
                    "required": {
                        "image": [
                            ["00282-3430329909-ad-before.png"],
                            {},
                        ]
                    }
                }
            },
            "LoadImageMask": {
                "input": {
                    "required": {
                        "image": [
                            ["00282-3430329909-ad-before.png"],
                            {},
                        ]
                    }
                }
            },
        },
    )

    image_spec = snapshot.field_specs_by_alias["Inpaint"]["load_image"]["image"]
    mask_spec = snapshot.field_specs_by_alias["Inpaint"]["load_image_as_mask"]["image"]

    assert image_spec.value == selected_image
    assert mask_spec.value == selected_mask
    assert cube.buffer["nodes"]["load_image"]["inputs"]["image"] == selected_image
    assert (
        cube.buffer["nodes"]["load_image_as_mask"]["inputs"]["image"] == selected_mask
    )
    assert cube.dirty is False


def test_checkpoint_field_no_longer_uses_node_specific_model_picker_patch() -> None:
    """Checkpoint fields should stay standard until value enrichment selects a picker."""

    cube = cube_state(
        nodes={
            "checkpoint": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model-a.safetensors"},
            },
            "ultralytics": {
                "class_type": "UltralyticsDetectorProvider",
                "inputs": {"model_name": "bbox/yolo.pt"},
            },
        }
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
                            {"default": "model-a.safetensors"},
                        ]
                    }
                }
            },
            "UltralyticsDetectorProvider": {
                "input": {
                    "required": {
                        "model_name": [
                            ["bbox/yolo.pt", "segm/yolo-seg.pt"],
                            {"default": "bbox/yolo.pt"},
                        ]
                    }
                }
            },
        },
    )

    checkpoint_behavior = snapshot.field_specs_by_alias["A"]["checkpoint"][
        "ckpt_name"
    ].field_behavior
    ultralytics_behavior = snapshot.field_specs_by_alias["A"]["ultralytics"][
        "model_name"
    ].field_behavior

    assert checkpoint_behavior.presentation == FieldPresentation.STANDARD
    assert checkpoint_behavior.style == {}
    assert ultralytics_behavior.presentation == FieldPresentation.STANDARD


def test_build_snapshot_marks_link_backed_sampler_fields_as_linked_without_rewrite() -> (
    None
):
    """Active sampler links should bypass literal canonicalization and remain linked."""

    cube = cube_state(
        nodes={
            "ksampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "legacy-sampler"},
                "sampler_link": {"from_cube": "A", "from_node": "upstream"},
            }
        }
    )
    snapshot = build_behavior_snapshot(
        cube_states={"B": cube},
        stack_order=["B"],
        definitions_by_class={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [["euler", "heun"], {}],
                    }
                }
            }
        },
    )

    spec = snapshot.field_specs_by_alias["B"]["ksampler"]["sampler_name"]

    assert spec.raw_value == "legacy-sampler"
    assert spec.value == "legacy-sampler"
    assert spec.value_source == FieldValueSource.LINKED
    assert cube.buffer["nodes"]["ksampler"]["inputs"]["sampler_name"] == (
        "legacy-sampler"
    )
    assert cube.dirty is False


def test_build_snapshot_prefers_live_options_over_compact_dynamic_cube_definition() -> (
    None
):
    """Compact dynamic cube metadata should hydrate from current live Comfy options."""

    cube = cube_state(
        nodes={
            "ksampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "heun"},
            }
        },
        definitions={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [
                            "LIST",
                            {"dynamic": True, "input_order": 1},
                        ],
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [
                            ["euler", "heun"],
                            {"default": "euler"},
                        ]
                    }
                }
            }
        },
    )

    spec = snapshot.field_specs_by_alias["A"]["ksampler"]["sampler_name"]

    assert extract_live_list_options(spec.field_info) == ("euler", "heun")
    assert spec.meta_info["options_resolved"] is True
    assert spec.meta_info["options_unavailable_reason"] is None
    assert spec.value == "heun"
    assert spec.value_source == FieldValueSource.EXPLICIT


def test_build_snapshot_ignores_compact_dynamic_list_marker_when_live_missing() -> None:
    """Offline compact dynamic LIST metadata must not become runtime metadata."""

    cube = cube_state(
        nodes={
            "ksampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "heun"},
            }
        },
        definitions={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [
                            "LIST",
                            {"dynamic": True, "input_order": 1},
                        ],
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )

    spec = snapshot.field_specs_by_alias["A"]["ksampler"]["sampler_name"]

    assert spec.field_type is None
    assert spec.field_info is None
    assert "options_resolved" not in spec.meta_info
    assert "options_unavailable_reason" not in spec.meta_info
    assert spec.value == "heun"
    assert spec.value_source == FieldValueSource.EXPLICIT


def test_build_snapshot_ignores_cube_authored_combo_options_when_live_missing() -> None:
    """Cube-authored COMBO options must not become authoritative choices."""

    cube = cube_state(
        nodes={
            "ksampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "cube_only"},
            }
        },
        definitions={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [
                            "COMBO",
                            {"options": ["cube_only"]},
                        ],
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["ksampler"]["sampler_name"]
    assert spec.field_type is None
    assert spec.field_info is None
    assert "options" not in spec.meta_info
    assert spec.value == "cube_only"


def test_build_snapshot_enriches_wrapper_choices_from_live_body_definition() -> None:
    """Wrapper fields should expose live body COMBO options when public metadata is compact."""

    wrapper_id = "de2c84e5-02a8-4c50-831d-3c169dee4820"
    cube = cube_state(
        nodes={
            "resize_by_factor": {
                "class_type": wrapper_id,
                "inputs": {"scheduler": "normal"},
            }
        },
        definitions={
            "SimpleSyrup.KSamplerExtras": {
                "input": {
                    "required": {
                        "scheduler": [
                            "LIST",
                            {"dynamic": True},
                        ],
                    }
                }
            }
        },
        subgraphs=[
            {
                "id": wrapper_id,
                "name": "Resize by Factor",
                "inputNode": {"id": -10},
                "inputs": [
                    {
                        "id": "scheduler-interface",
                        "name": "scheduler",
                        "label": "Scheduler",
                        "type": "COMBO",
                        "linkIds": [1169],
                    },
                ],
                "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
                "links": [
                    {
                        "id": 1169,
                        "origin_id": -10,
                        "target_id": 1661,
                        "target_slot": 0,
                        "type": "COMBO",
                    }
                ],
                "nodes": [
                    {
                        "id": 1661,
                        "type": "SimpleSyrup.KSamplerExtras",
                        "inputs": [
                            {
                                "link": 1169,
                                "localized_name": "scheduler",
                                "name": "scheduler",
                                "type": "COMBO",
                                "widget": {"name": "scheduler"},
                            }
                        ],
                        "widgets_values": ["normal"],
                    }
                ],
            }
        ],
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "SimpleSyrup.KSamplerExtras": {
                "input": {
                    "required": {
                        "scheduler": [
                            ["normal", "karras"],
                            {"default": "normal"},
                        ],
                    }
                }
            }
        },
    )

    spec = snapshot.field_specs_by_alias["A"]["resize_by_factor"]["scheduler"]

    assert spec.field_type == "LIST"
    assert extract_live_list_options(spec.field_info) == ("normal", "karras")
    assert spec.meta_info["options_resolved"] is True
    assert spec.meta_info["options_unavailable_reason"] is None
    assert spec.value == "normal"
    assert spec.value_source == FieldValueSource.EXPLICIT


def test_build_snapshot_renders_wrapper_combo_without_default_or_input() -> None:
    """Wrapper COMBO fields with live options should render without stored values."""

    wrapper_id = "de2c84e5-02a8-4c50-831d-3c169dee4820"
    service = NodeBehaviorService(
        node_definition_gateway=RequiredOnlyNodeDefinitionGateway(
            {
                "UpscaleModelLoader": {
                    "input": {
                        "required": {
                            "model_name": [
                                "COMBO",
                                {
                                    "options": [
                                        "ESRGAN_4x.pth",
                                        "R-ESRGAN 4x+ Anime6B.pth",
                                    ]
                                },
                            ]
                        }
                    },
                }
            }
        )
    )
    cube = cube_state(
        nodes={
            "resize_by_factor": {
                "class_type": wrapper_id,
                "inputs": {},
            }
        },
        definitions={},
        subgraphs=[
            {
                "id": wrapper_id,
                "name": "Resize by Factor",
                "inputNode": {"id": -10},
                "inputs": [
                    {
                        "id": "model-name-interface",
                        "name": "model_name",
                        "label": "Model",
                        "type": "COMBO",
                        "linkIds": [1169],
                    },
                ],
                "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
                "links": [
                    {
                        "id": 1169,
                        "origin_id": -10,
                        "target_id": 1661,
                        "target_slot": 0,
                        "type": "COMBO",
                    }
                ],
                "nodes": [
                    {
                        "id": 1661,
                        "type": "UpscaleModelLoader",
                        "inputs": [
                            {
                                "link": 1169,
                                "localized_name": "model_name",
                                "name": "model_name",
                                "type": "COMBO",
                                "widget": {"name": "model_name"},
                            }
                        ],
                        "widgets_values": [],
                    }
                ],
            }
        ],
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["resize_by_factor"]["model_name"]
    assert spec.field_type == "COMBO"
    assert extract_live_list_options(spec.field_info) == (
        "ESRGAN_4x.pth",
        "R-ESRGAN 4x+ Anime6B.pth",
    )
    assert spec.value == "ESRGAN_4x.pth"
    assert spec.value_source == FieldValueSource.FIRST_OPTION


def test_build_snapshot_preserves_wrapper_combo_widget_default() -> None:
    """Wrapper body widget values should remain defaults after live COMBO enrichment."""

    wrapper_id = "de2c84e5-02a8-4c50-831d-3c169dee4820"
    service = NodeBehaviorService(
        node_definition_gateway=RequiredOnlyNodeDefinitionGateway(
            {
                "UpscaleModelLoader": {
                    "input": {
                        "required": {
                            "model_name": [
                                "COMBO",
                                {
                                    "options": [
                                        "ESRGAN_4x.pth",
                                        "R-ESRGAN 4x+ Anime6B.pth",
                                    ]
                                },
                            ]
                        }
                    },
                }
            }
        )
    )
    cube = cube_state(
        nodes={
            "resize_by_factor": {
                "class_type": wrapper_id,
                "inputs": {},
            }
        },
        definitions={},
        subgraphs=[
            {
                "id": wrapper_id,
                "name": "Resize by Factor",
                "inputNode": {"id": -10},
                "inputs": [
                    {
                        "id": "model-name-interface",
                        "name": "model_name",
                        "label": "Model",
                        "type": "COMBO",
                        "linkIds": [1169],
                    },
                ],
                "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
                "links": [
                    {
                        "id": 1169,
                        "origin_id": -10,
                        "target_id": 1661,
                        "target_slot": 0,
                        "type": "COMBO",
                    }
                ],
                "nodes": [
                    {
                        "id": 1661,
                        "type": "UpscaleModelLoader",
                        "inputs": [
                            {
                                "link": 1169,
                                "localized_name": "model_name",
                                "name": "model_name",
                                "type": "COMBO",
                                "widget": {"name": "model_name"},
                            }
                        ],
                        "widgets_values": ["R-ESRGAN 4x+ Anime6B.pth"],
                    }
                ],
            }
        ],
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["resize_by_factor"]["model_name"]
    assert spec.meta_info["default"] == "R-ESRGAN 4x+ Anime6B.pth"
    assert spec.value == "R-ESRGAN 4x+ Anime6B.pth"
    assert spec.value_source == FieldValueSource.AUTHORED_DEFAULT


def test_build_snapshot_resolves_combo_choice_fields() -> None:
    """COMBO fields should resolve through the same choice-value path as LIST fields."""

    cube = cube_state(
        nodes={
            "load_upscale_model": {
                "class_type": "UpscaleModelLoader",
                "inputs": {"model_name": "R-ESRGAN 4x+ Anime6B.pth"},
            }
        },
        definitions={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )

    spec = snapshot.field_specs_by_alias["A"]["load_upscale_model"]["model_name"]

    assert spec.field_type == "COMBO"
    assert extract_live_list_options(spec.field_info) == (
        "ESRGAN_4x.pth",
        "R-ESRGAN 4x+ Anime6B.pth",
    )
    assert spec.value == "R-ESRGAN 4x+ Anime6B.pth"
    assert spec.value_source == FieldValueSource.EXPLICIT


def test_build_snapshot_adds_model_icon_for_non_rich_model_host() -> None:
    """Model-backed ordinary COMBO hosts should receive the default model icon."""

    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "UpscaleModelLoader": {
                    "input": {
                        "required": {
                            "model_name": [
                                "COMBO",
                                {
                                    "options": [
                                        "ESRGAN_4x.pth",
                                        "R-ESRGAN 4x+ Anime6B.pth",
                                    ]
                                },
                            ]
                        }
                    },
                }
            }
        ),
        model_backed_node_detector=_model_detector(
            _model_item("upscale_models", "R-ESRGAN 4x+ Anime6B.pth"),
            kinds=("upscale_models",),
        ),
    )
    cube = cube_state(
        nodes={
            "load_upscale_model": {
                "class_type": "UpscaleModelLoader",
                "inputs": {"model_name": "R-ESRGAN 4x+ Anime6B.pth"},
            }
        },
        definitions={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    behavior = snapshot.resolved_nodes_by_alias["A"]["load_upscale_model"]
    spec = snapshot.field_specs_by_alias["A"]["load_upscale_model"]["model_name"]
    assert behavior.card.icon_name == "model"
    assert spec.field_behavior.presentation == FieldPresentation.STANDARD


def test_build_snapshot_uses_host_model_icon_for_checkpoint_loader() -> None:
    """Checkpoint graphical picker hosts should receive the built-in model icon."""

    cube = cube_state(
        nodes={
            "checkpoint": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "Anime\\preview.safetensors"},
            }
        },
        definitions={
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {
                        "ckpt_name": [
                            [
                                "Anime\\preview.safetensors",
                                "Realism\\base.safetensors",
                            ],
                            {},
                        ]
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert snapshot.resolved_nodes_by_alias["A"]["checkpoint"].card.icon_name == "model"


def test_build_snapshot_uses_host_model_icon_for_vae_loader() -> None:
    """VAE graphical picker hosts should receive the built-in model icon."""

    cube = cube_state(
        nodes={
            "vae": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "ClearVAE.safetensors"},
            }
        },
        definitions={
            "VAELoader": {
                "input": {
                    "required": {
                        "vae_name": [["ClearVAE.safetensors", "OtherVAE.pt"], {}]
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert snapshot.resolved_nodes_by_alias["A"]["vae"].card.icon_name == "model"


def test_build_snapshot_adds_model_icon_for_explicit_model_picker_field() -> None:
    """Explicit graphical model picker fields should receive the default model icon."""

    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "CheckpointLoaderSimple": {
                    "input": {"required": {"ckpt_name": ["STRING", {}]}},
                }
            }
        )
    )
    cube = cube_state(
        nodes={
            "checkpoint": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {},
            }
        },
        definitions={
            "CheckpointLoaderSimple": {
                "input": {"required": {"ckpt_name": ["STRING", {}]}},
            }
        },
    )
    runtime_state = service.ensure_runtime_state(cube)
    runtime_state.node_instance_patch = PackageBehaviorPatch(
        by_node_instance={
            "A:checkpoint": NodeBehaviorPatch(
                field_patches={
                    "ckpt_name": FieldBehaviorPatch(
                        presentation=FieldPresentation.MODEL_PICKER,
                        style={"model_kind": "checkpoints"},
                    )
                }
            )
        }
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    behavior = snapshot.resolved_nodes_by_alias["A"]["checkpoint"]
    spec = snapshot.field_specs_by_alias["A"]["checkpoint"]["ckpt_name"]
    assert behavior.card.icon_name == "model"
    assert spec.field_behavior.presentation == FieldPresentation.MODEL_PICKER


def test_build_snapshot_preserves_explicit_icon_for_model_backed_node() -> None:
    """Explicit host icons should win over the default model icon."""

    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(),
        model_backed_node_detector=_model_detector(
            _model_item("upscale_models", "R-ESRGAN 4x+ Anime6B.pth"),
            kinds=("upscale_models",),
        ),
    )
    cube = cube_state(
        nodes={
            "vectorscopecc": {
                "class_type": "VectorscopeCC",
                "inputs": {
                    "model_name": "R-ESRGAN 4x+ Anime6B.pth",
                    "brightness": 0.5,
                },
            }
        },
        definitions={
            "VectorscopeCC": {
                "input": {
                    "required": {
                        "model_name": [
                            ["R-ESRGAN 4x+ Anime6B.pth"],
                            {},
                        ],
                        "brightness": ["FLOAT", {"min": 0, "max": 1, "step": 0.01}],
                    }
                },
            }
        },
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert snapshot.resolved_nodes_by_alias["A"]["vectorscopecc"].card.icon_name == (
        "palette"
    )


def test_build_snapshot_without_model_detector_leaves_model_host_uniconed() -> None:
    """Default behavior should remain unchanged when no detector is composed."""

    cube = cube_state(
        nodes={
            "load_upscale_model": {
                "class_type": "UpscaleModelLoader",
                "inputs": {"model_name": "R-ESRGAN 4x+ Anime6B.pth"},
            }
        },
        definitions={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {"options": ["R-ESRGAN 4x+ Anime6B.pth"]},
                        ]
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )

    assert (
        snapshot.resolved_nodes_by_alias["A"]["load_upscale_model"].card.icon_name
        is None
    )


def test_build_snapshot_does_not_icon_non_model_list_node() -> None:
    """Ordinary LIST hosts should not receive the model icon."""

    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(),
        model_backed_node_detector=_model_detector(
            _model_item("checkpoints", "SDXL/base.safetensors"),
            kinds=("checkpoints",),
        ),
    )
    cube = cube_state(
        nodes={
            "mode_selector": {
                "class_type": "ModeSelector",
                "inputs": {"mode": "fast"},
            }
        },
        definitions={
            "ModeSelector": {
                "input": {"required": {"mode": [["fast", "accurate"], {}]}},
            }
        },
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert snapshot.resolved_nodes_by_alias["A"]["mode_selector"].card.icon_name is None


def test_build_snapshot_resolves_missing_combo_to_first_option() -> None:
    """COMBO fields without authored values should fall back to their first option."""

    cube = cube_state(
        nodes={
            "load_upscale_model": {
                "class_type": "UpscaleModelLoader",
                "inputs": {},
            }
        },
        definitions={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )

    spec = snapshot.field_specs_by_alias["A"]["load_upscale_model"]["model_name"]

    assert spec.field_type == "COMBO"
    assert spec.value == "ESRGAN_4x.pth"
    assert spec.value_source == FieldValueSource.FIRST_OPTION


class _FakeModelCatalog:
    """Return deterministic model catalog rows for behavior-service tests."""

    def __init__(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Store fake model rows grouped by kind."""

        self._items_by_kind: dict[str, list[ModelCatalogItem]] = {}
        for item in items:
            self._items_by_kind.setdefault(item.kind, []).append(item)

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return configured rows for one model kind."""

        return tuple(self._items_by_kind.get(kind, ()))

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return configured rows through the refresh API."""

        return self.list_models(kind)

    def invalidate(self, kind: str | None = None) -> None:
        """Ignore invalidation in deterministic tests."""

        _ = kind


def _model_detector(
    *items: ModelCatalogItem,
    kinds: tuple[str, ...],
) -> ModelBackedNodeDetector:
    """Return a model-backed detector for behavior-service tests."""

    return ModelBackedNodeDetector(
        model_catalog=_FakeModelCatalog(items),
        model_kinds=kinds,
    )


def _model_item(kind: str, value: str) -> ModelCatalogItem:
    """Return one minimal model catalog item for behavior-service tests."""

    normalized = value.replace("\\", "/")
    filename = normalized.rsplit("/", 1)[-1]
    basename = filename.rsplit(".", 1)[0]
    folder = normalized.rsplit("/", 1)[0] if "/" in normalized else ""
    return ModelCatalogItem(
        kind=kind,
        display_name=basename,
        display_subtitle=None,
        backend_value=value,
        relative_path=value,
        folder=folder,
        basename=basename,
        extension=f".{filename.rsplit('.', 1)[1]}" if "." in filename else "",
        thumbnail_variants=(),
        base_model=None,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=f"{basename} {value}".replace("\\", "/").casefold(),
    )
