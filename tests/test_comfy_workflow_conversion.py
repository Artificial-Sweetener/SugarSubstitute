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

"""Verify direct Comfy workflow conversion and API graph construction."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

from substitute.application.direct_workflows import DirectWorkflowGenerationPlanService
from substitute.application.ports import NodeDefinitionHydrationResult
from substitute.domain.comfy_workflow import (
    ComfyApiGraphBuildError,
    ComfyApiGraphBuilder,
    ComfyWorkflowConverter,
    DirectWorkflowState,
)
from substitute.application.node_behavior import (
    CardMode,
    FieldPresentation,
    NodeBehaviorService,
    PromptRole,
)
from tests.node_behavior_test_helpers import build_behavior_snapshot


class _NoNodeDefinitions:
    """Satisfy node behavior construction for activation-only tests."""

    def get_node_definition(self, class_type: str) -> dict[str, object]:
        """Return no live definition for the unused class lookup."""

        _ = class_type
        return {}

    def get_required_node_definition(self, class_type: str) -> dict[str, object]:
        """Return no required live definition for the unused class lookup."""

        _ = class_type
        return {}


def test_converter_maps_widgets_links_titles_modes_and_orderable_ids() -> None:
    """A conventional UI graph should become one editable API-shaped graph."""

    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "title": "Load model",
                "inputs": [
                    {
                        "name": "ckpt_name",
                        "type": "COMBO",
                        "widget": {"name": "ckpt_name"},
                        "link": None,
                    }
                ],
                "outputs": [{"name": "MODEL", "type": "MODEL"}],
                "widgets_values": ["model.safetensors"],
            },
            {
                "id": 2,
                "type": "KSampler",
                "mode": 4,
                "inputs": [
                    {"name": "model", "type": "MODEL", "link": 10},
                    {
                        "name": "seed",
                        "type": "INT",
                        "widget": {"name": "seed"},
                        "link": None,
                    },
                    {
                        "name": "steps",
                        "type": "INT",
                        "widget": {"name": "steps"},
                        "link": None,
                    },
                ],
                "outputs": [{"name": "LATENT", "type": "LATENT"}],
                "widgets_values": [123, "randomize", 20],
            },
        ],
        "links": [[10, 1, 0, 2, 0, "MODEL"]],
    }

    graph = ComfyWorkflowConverter().convert(workflow)

    assert graph["nodes"]["1"]["inputs"] == {  # type: ignore[index]
        "ckpt_name": "model.safetensors"
    }
    sampler = graph["nodes"]["2"]  # type: ignore[index]
    assert sampler["inputs"] == {"model": ["1", 0], "seed": 123, "steps": 20}
    assert sampler["mode"] == 4
    assert sampler["_meta"] == {"title": "KSampler"}


def test_converter_flattens_subgraph_and_preserves_internal_defaults() -> None:
    """Bundled-style subgraphs should flatten without requiring root widget values."""

    subgraph_id = "31d70bc1-12a1-4af4-8a84-c335621fe232"
    workflow = {
        "nodes": [
            {
                "id": 7,
                "type": subgraph_id,
                "title": "Text to Image",
                "inputs": [
                    {
                        "name": "prompt",
                        "type": "STRING",
                        "widget": {"name": "prompt"},
                        "link": None,
                    }
                ],
                "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
                "widgets_values": [],
                "properties": {"proxyWidgets": [["12", "text"]]},
            }
        ],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "id": subgraph_id,
                    "name": "local-Text to Image",
                    "inputs": [{"name": "prompt", "type": "STRING"}],
                    "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
                    "nodes": [
                        {
                            "id": 12,
                            "type": "CLIPTextEncode",
                            "inputs": [
                                {
                                    "name": "text",
                                    "type": "STRING",
                                    "widget": {"name": "text"},
                                    "link": 1,
                                }
                            ],
                            "outputs": [
                                {"name": "CONDITIONING", "type": "CONDITIONING"}
                            ],
                            "widgets_values": ["internal prompt"],
                        },
                        {
                            "id": 13,
                            "type": "PreviewImage",
                            "inputs": [
                                {"name": "images", "type": "IMAGE", "link": None}
                            ],
                            "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
                        },
                    ],
                    "links": [
                        {
                            "id": 1,
                            "origin_id": -10,
                            "origin_slot": 0,
                            "target_id": 12,
                            "target_slot": 0,
                            "type": "STRING",
                        },
                        {
                            "id": 2,
                            "origin_id": 13,
                            "origin_slot": 0,
                            "target_id": -20,
                            "target_slot": 0,
                            "type": "IMAGE",
                        },
                    ],
                }
            ]
        },
    }

    graph = ComfyWorkflowConverter().convert(workflow)

    assert tuple(graph["nodes"]) == ("7:12", "7:13")  # type: ignore[arg-type]
    encoder = graph["nodes"]["7:12"]  # type: ignore[index]
    assert encoder["inputs"]["text"] == "internal prompt"
    assert encoder["_meta"]["title"] == "Text to Image / CLIPTextEncode"


def test_converter_resolves_frontend_reroute_nodes() -> None:
    """Reroutes should disappear while their upstream link remains executable."""

    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "inputs": [],
                "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
            },
            {
                "id": 2,
                "type": "Reroute",
                "inputs": [{"name": "", "type": "*", "link": 1}],
                "outputs": [{"name": "", "type": "*"}],
            },
            {
                "id": 3,
                "type": "PreviewImage",
                "inputs": [{"name": "images", "type": "IMAGE", "link": 2}],
                "outputs": [],
            },
        ],
        "links": [
            [1, 1, 0, 2, 0, "IMAGE"],
            [2, 2, 0, 3, 0, "IMAGE"],
        ],
    }

    graph = ComfyWorkflowConverter().convert(workflow)

    assert "2" not in graph["nodes"]  # type: ignore[operator]
    assert graph["nodes"]["3"]["inputs"]["images"] == ["1", 0]  # type: ignore[index]


def test_converter_omits_frontend_markdown_notes() -> None:
    """Markdown annotations should require no card, definition, or API node."""

    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "MarkdownNote",
                "inputs": [],
                "outputs": [],
                "widgets_values": ["# SDXL workflow instructions"],
            },
            {
                "id": 2,
                "type": "EmptyLatentImage",
                "inputs": [
                    {
                        "name": "width",
                        "type": "INT",
                        "widget": {"name": "width"},
                        "link": None,
                    }
                ],
                "outputs": [{"name": "LATENT", "type": "LATENT"}],
                "widgets_values": [1024],
            },
        ],
        "links": [],
    }

    graph = ComfyWorkflowConverter().convert(workflow)
    payload = ComfyApiGraphBuilder().build(graph)

    assert tuple(graph["nodes"]) == ("2",)  # type: ignore[arg-type]
    assert tuple(payload) == ("2",)


def test_converter_preserves_primitive_as_one_field_value_proxy() -> None:
    """Primitive widgets should remain editable without becoming API nodes."""

    workflow = {
        "nodes": [
            {
                "id": 45,
                "type": "PrimitiveNode",
                "title": "steps",
                "inputs": [],
                "outputs": [
                    {
                        "name": "INT",
                        "type": "INT",
                        "widget": {"name": "steps"},
                        "links": [38, 41],
                    }
                ],
                "widgets_values": [25, "fixed"],
            },
            {
                "id": 10,
                "type": "KSamplerAdvanced",
                "inputs": [
                    {
                        "name": "steps",
                        "type": "INT",
                        "widget": {"name": "steps"},
                        "link": 41,
                    }
                ],
                "outputs": [],
                "widgets_values": [25],
            },
            {
                "id": 11,
                "type": "KSamplerAdvanced",
                "inputs": [
                    {
                        "name": "steps",
                        "type": "INT",
                        "widget": {"name": "steps"},
                        "link": 38,
                    }
                ],
                "outputs": [],
                "widgets_values": [25],
            },
        ],
        "links": [
            [38, 45, 0, 11, 0, "INT"],
            [41, 45, 0, 10, 0, "INT"],
        ],
    }

    graph = ComfyWorkflowConverter().convert(workflow)

    primitive = graph["nodes"]["45"]  # type: ignore[index]
    assert primitive["inputs"] == {"steps": 25}
    assert primitive["_meta"] == {"title": "steps"}
    assert primitive["_workflow"]["execution_role"] == "value_proxy"
    assert primitive["_workflow"]["editor_definition"] == {
        "input": {"required": {"steps": ["INT", {"default": 25}]}}
    }

    primitive["inputs"]["steps"] = 31
    payload = ComfyApiGraphBuilder().build(graph)

    assert "45" not in payload
    assert payload["10"]["inputs"]["steps"] == 31  # type: ignore[index]
    assert payload["11"]["inputs"]["steps"] == 31  # type: ignore[index]


def test_direct_workflow_prompt_detection_uses_upstream_primitive_owner() -> None:
    """Converted value proxies should receive prompt behavior through typed flow."""

    definitions: dict[str, Mapping[str, object]] = {
        "ThirdPartyTextEncoder": {
            "input": {
                "required": {
                    "text": ["STRING", {"multiline": True}],
                }
            },
            "output": ["CONDITIONING"],
        },
        "ThirdPartySampler": {
            "input": {
                "required": {
                    "positive": ["CONDITIONING", {}],
                }
            }
        },
    }
    workflow = {
        "nodes": [
            {
                "id": 45,
                "type": "PrimitiveNode",
                "title": "Text",
                "inputs": [],
                "outputs": [
                    {
                        "name": "STRING",
                        "type": "STRING",
                        "widget": {"name": "text"},
                        "links": [1],
                    }
                ],
                "widgets_values": ["a lighthouse"],
            },
            {
                "id": 2,
                "type": "ThirdPartyTextEncoder",
                "inputs": [{"name": "text", "type": "STRING", "link": 1}],
                "outputs": [
                    {
                        "name": "CONDITIONING",
                        "type": "CONDITIONING",
                        "links": [2],
                    }
                ],
                "widgets_values": [],
            },
            {
                "id": 3,
                "type": "ThirdPartySampler",
                "inputs": [{"name": "positive", "type": "CONDITIONING", "link": 2}],
                "outputs": [],
                "widgets_values": [],
            },
        ],
        "links": [
            [1, 45, 0, 2, 0, "STRING"],
            [2, 2, 0, 3, 0, "CONDITIONING"],
        ],
    }
    graph = ComfyWorkflowConverter().convert(
        workflow,
        node_definitions=definitions,
    )
    state = DirectWorkflowState(
        source_path=Path("workflow.json"),
        source_workflow=workflow,
        buffer=graph,
    )

    snapshot = build_behavior_snapshot(
        cube_states={"direct": state},
        stack_order=["direct"],
        definitions_by_class=definitions,
    )

    primitive = snapshot.resolved_nodes_by_alias["direct"]["45"]
    assert primitive.card.card_mode == CardMode.PROMPT
    assert primitive.fields["text"].presentation == FieldPresentation.PROMPT_BOX
    assert primitive.fields["text"].prompt is not None
    assert primitive.fields["text"].prompt.role == PromptRole.POSITIVE


def test_converter_builds_workflow_local_definitions_for_regular_widgets() -> None:
    """Serialized Comfy widgets should remain renderable without live metadata."""

    workflow = {
        "nodes": [
            {
                "id": 7,
                "type": "MissingCustomNode",
                "title": "Custom settings",
                "inputs": [
                    {
                        "name": "amount",
                        "type": "FLOAT",
                        "widget": {"name": "amount"},
                        "link": None,
                    }
                ],
                "outputs": [],
                "widgets_values": [0.75],
            }
        ],
        "links": [],
    }

    graph = ComfyWorkflowConverter().convert(workflow)

    node = graph["nodes"]["7"]  # type: ignore[index]
    assert node["inputs"] == {"amount": 0.75}
    assert node["_workflow"]["execution_role"] == "executable"
    assert node["_workflow"]["editor_definition"] == {
        "input": {"required": {"amount": ["FLOAT", {"default": 0.75}]}}
    }


def test_converter_decodes_dynamic_combo_and_nested_widget_values() -> None:
    """Dynamic selectors must own nested values without shifting later scalars."""

    definitions: dict[str, Mapping[str, object]] = {
        "NativeDynamicNode": {
            "input": {
                "required": {
                    "model": [
                        "COMFY_DYNAMICCOMBO_V3",
                        {
                            "options": [
                                {
                                    "key": "Quality",
                                    "inputs": {
                                        "required": {
                                            "prompt": [
                                                "STRING",
                                                {"default": "", "multiline": True},
                                            ],
                                            "resolution": [
                                                "COMBO",
                                                {"options": ["720p", "1080p"]},
                                            ],
                                            "duration": [
                                                "INT",
                                                {"default": 5, "min": 1, "max": 10},
                                            ],
                                            "references": [
                                                "COMFY_AUTOGROW_V3",
                                                {"template": {}},
                                            ],
                                        },
                                        "optional": {
                                            "upscale": [
                                                "BOOLEAN",
                                                {"default": False},
                                            ]
                                        },
                                    },
                                }
                            ]
                        },
                    ],
                    "seed": [
                        "INT",
                        {"default": 0, "control_after_generate": True},
                    ],
                    "watermark": ["BOOLEAN", {"default": False}],
                }
            }
        }
    }
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "NativeDynamicNode",
                "inputs": [],
                "outputs": [],
                "widgets_values": [
                    "Quality",
                    "a lighthouse",
                    "1080p",
                    7,
                    True,
                    42,
                    "randomize",
                    False,
                ],
            }
        ],
        "links": [],
    }

    graph = ComfyWorkflowConverter().convert(
        workflow,
        node_definitions=definitions,
    )

    node = graph["nodes"]["1"]  # type: ignore[index]
    assert node["inputs"] == {
        "model": "Quality",
        "model.prompt": "a lighthouse",
        "model.resolution": "1080p",
        "model.duration": 7,
        "model.upscale": True,
        "seed": 42,
        "watermark": False,
    }
    required = node["_workflow"]["editor_definition"]["input"]["required"]
    assert required["model"][0] == "COMBO"
    assert required["model"][1]["options"] == ["Quality"]
    assert required["model.prompt"][0] == "STRING"
    assert required["model.resolution"][0] == "COMBO"
    assert required["model.duration"][0] == "INT"
    assert required["seed"][1]["default"] == 42
    assert required["watermark"][1]["default"] is False


def test_converter_skips_load3d_frontend_values_before_dimensions() -> None:
    """Load3D buttons and viewport state must not shift width and height values."""

    definitions: dict[str, Mapping[str, object]] = {
        "Load3D": {
            "input": {
                "required": {
                    "model_file": ["COMBO", {"options": ["none"]}],
                    "image": ["LOAD_3D", {}],
                    "width": ["INT", {"default": 1024}],
                    "height": ["INT", {"default": 1024}],
                }
            }
        }
    }
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "Load3D",
                "inputs": [],
                "outputs": [],
                "widgets_values": [
                    "none",
                    "upload3dmodel",
                    "uploadExtraResources",
                    "clear",
                    "",
                    768,
                    512,
                ],
            }
        ],
        "links": [],
    }

    graph = ComfyWorkflowConverter().convert(
        workflow,
        node_definitions=definitions,
    )

    node = graph["nodes"]["1"]  # type: ignore[index]
    assert node["inputs"] == {
        "model_file": "none",
        "width": 768,
        "height": 512,
    }


def test_converter_honors_native_widget_type_override_for_union_socket() -> None:
    """A widgetType annotation should expose the native editor for a union socket."""

    definitions: dict[str, Mapping[str, object]] = {
        "Preview3D": {
            "input": {
                "required": {
                    "model_file": [
                        "STRING,FILE_3D",
                        {"default": "", "widgetType": "STRING"},
                    ]
                }
            }
        }
    }
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "Preview3D",
                "inputs": [],
                "outputs": [],
                "widgets_values": ["model.glb", ""],
            }
        ],
        "links": [],
    }

    graph = ComfyWorkflowConverter().convert(
        workflow,
        node_definitions=definitions,
    )

    node = graph["nodes"]["1"]  # type: ignore[index]
    assert node["inputs"] == {"model_file": "model.glb"}
    field = node["_workflow"]["editor_definition"]["input"]["required"]["model_file"]
    assert field == [
        "STRING",
        {
            "default": "model.glb",
            "widgetType": "STRING",
            "native_socket_type": "STRING,FILE_3D",
        },
    ]


def test_api_builder_strips_metadata_and_rewires_bypassed_node() -> None:
    """Comfy bypass should remove the node and route compatible connections."""

    graph = {
        "nodes": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": "input.png"},
                "mode": 0,
                "_workflow": {"inputs": [], "outputs": []},
            },
            "2": {
                "class_type": "ImageScale",
                "inputs": {"image": ["1", 0], "width": 512},
                "mode": 4,
                "_meta": {"title": "Optional scale"},
                "_workflow": {
                    "inputs": [
                        {"name": "image", "type": "IMAGE"},
                        {"name": "width", "type": "INT"},
                    ],
                    "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
                },
            },
            "3": {
                "class_type": "PreviewImage",
                "inputs": {"images": ["2", 0]},
                "mode": 0,
                "_workflow": {"inputs": [], "outputs": []},
            },
        }
    }

    payload = ComfyApiGraphBuilder().build(graph)

    assert tuple(payload) == ("1", "3")
    assert payload["3"]["inputs"]["images"] == ["1", 0]  # type: ignore[index]
    assert "mode" not in payload["1"]  # type: ignore[operator]
    assert "_workflow" not in payload["1"]  # type: ignore[operator]


def test_api_builder_disconnects_unroutable_bypass_output() -> None:
    """An unmatched bypass output should behave like Comfy's disconnected link."""

    graph = {
        "nodes": {
            "1": {
                "class_type": "Constant",
                "inputs": {},
                "mode": 4,
                "_workflow": {
                    "inputs": [],
                    "outputs": [{"name": "VALUE", "type": "INT"}],
                },
            },
            "2": {
                "class_type": "Consumer",
                "inputs": {"value": ["1", 0]},
                "mode": 0,
            },
        }
    }

    payload = ComfyApiGraphBuilder().build(graph)

    assert payload["2"]["inputs"] == {}  # type: ignore[index]


def test_direct_workflow_activation_uses_comfy_mode() -> None:
    """The shared node switch should persist direct state as Comfy bypass mode."""

    state = DirectWorkflowState(
        source_path=Path("workflow.json"),
        source_workflow={"nodes": [], "links": []},
        buffer={"nodes": {"9": {"class_type": "PreviewImage", "inputs": {}}}},
    )

    state.set_node_activation("9", enabled=False)

    assert state.buffer["nodes"]["9"]["mode"] == 4  # type: ignore[index]
    assert state.dirty is True


def test_shared_node_behavior_toggle_uses_direct_comfy_bypass_mode() -> None:
    """Shared editor toggle orchestration should not write Sugar enabled fields."""

    state = DirectWorkflowState(
        source_path=Path("workflow.json"),
        source_workflow={"nodes": [], "links": []},
        buffer={
            "nodes": {"9": {"class_type": "PreviewImage", "inputs": {}, "mode": 0}}
        },
    )
    service = NodeBehaviorService(node_definition_gateway=_NoNodeDefinitions())

    service.toggle_node_activation_override(state, "9")

    node = state.buffer["nodes"]["9"]  # type: ignore[index]
    assert node["mode"] == 4
    assert "enabled" not in node

    service.toggle_node_activation_override(state, "9")

    assert node["mode"] == 0


def test_execution_preflight_checks_only_active_backend_classes() -> None:
    """Frontend proxies and authored bypass nodes should not require backend classes."""

    class _Hydrator:
        """Record active classes and report the custom executable unavailable."""

        def __init__(self) -> None:
            self.requested: tuple[str, ...] = ()

        def ensure_node_definitions(
            self,
            node_classes: Iterable[str],
        ) -> NodeDefinitionHydrationResult:
            self.requested = tuple(node_classes)
            return NodeDefinitionHydrationResult(
                requested=self.requested,
                available=(),
                unavailable=self.requested,
            )

    hydrator = _Hydrator()
    document = DirectWorkflowState(
        source_path=Path("workflow.json"),
        source_workflow={"nodes": [], "links": []},
        buffer={
            "nodes": {
                "1": {
                    "class_type": "PrimitiveNode",
                    "inputs": {"amount": 2},
                    "_workflow": {
                        "execution_role": "value_proxy",
                        "value_field": "amount",
                    },
                },
                "2": {
                    "class_type": "MissingCustomNode",
                    "inputs": {"amount": ["1", 0]},
                    "_workflow": {"execution_role": "executable"},
                },
                "3": {
                    "class_type": "BypassedOptionalNode",
                    "inputs": {},
                    "mode": 4,
                    "_workflow": {"execution_role": "executable"},
                },
            }
        },
    )
    service = DirectWorkflowGenerationPlanService(node_definition_hydrator=hydrator)

    with pytest.raises(ComfyApiGraphBuildError, match="MissingCustomNode"):
        service.build(document)

    assert hydrator.requested == ("MissingCustomNode",)
