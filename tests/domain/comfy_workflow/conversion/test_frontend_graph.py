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

"""Verify frontend Comfy workflow graph conversion."""

from __future__ import annotations

from substitute.domain.comfy_workflow import (
    ComfyApiGraphBuilder,
    ComfyWorkflowConverter,
)


def test_converter_maps_widgets_links_titles_modes_and_orderable_ids() -> None:
    """Convert a conventional UI graph into one editable API-shaped graph."""
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
    """Flatten bundled subgraphs without requiring root widget values."""
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
    """Remove reroutes while retaining their executable upstream link."""
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
    assert graph["nodes"]["3"]["inputs"]["images"] == [  # type: ignore[index]
        "1",
        0,
    ]


def test_converter_omits_frontend_markdown_notes() -> None:
    """Exclude annotations from cards, definitions, and API nodes."""
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
    """Keep primitive widgets editable without creating API nodes."""
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
