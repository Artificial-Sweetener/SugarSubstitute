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

"""Verify editor-definition reconstruction during workflow conversion."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.domain.comfy_workflow import ComfyWorkflowConverter


def test_converter_builds_workflow_local_definitions_for_regular_widgets() -> None:
    """Keep serialized widgets renderable without live metadata."""
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


def test_converter_preserves_node_advanced_disclosure_state() -> None:
    """Keep Comfy's serialized Nodes 2.0 disclosure state as editor metadata."""

    workflow = {
        "nodes": [
            {
                "id": 7,
                "type": "AdvancedNode",
                "showAdvanced": True,
                "inputs": [],
                "outputs": [],
                "widgets_values": [],
            }
        ],
        "links": [],
    }

    graph = ComfyWorkflowConverter().convert(workflow)

    node = graph["nodes"]["7"]  # type: ignore[index]
    assert node["_workflow"]["show_advanced_inputs"] is True


def test_converter_decodes_dynamic_combo_and_nested_widget_values() -> None:
    """Keep nested selector values from shifting later scalar values."""
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
    """Keep Load3D buttons and viewport state from shifting dimensions."""
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
    """Expose the native editor declared for a union socket."""
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


def test_converter_preserves_native_palette_documents() -> None:
    """Decode a structured COLORS value without shifting later scalar fields."""

    definitions: dict[str, Mapping[str, object]] = {
        "PaletteNode": {
            "input": {
                "required": {
                    "color_palette": ["COLORS", {"default": []}],
                    "width": ["INT", {"default": 1024}],
                }
            }
        }
    }
    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "PaletteNode",
                "inputs": [],
                "outputs": [],
                "widgets_values": [["#112233", "#abcdef"], 768],
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
        "color_palette": ["#112233", "#abcdef"],
        "width": 768,
    }
