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

"""Subgraph-wrapper graph fixtures."""

from __future__ import annotations


UUID_WRAPPER = "644694cf-354b-4cc8-8a67-a78145a8180e"
UUID_NESTED_WRAPPER = "8f6c43da-07af-4666-9e9a-0b4c7f83bdad"


def _runtime_graph() -> dict[str, object]:
    """Build a runtime graph with one surface wrapper and one matching subgraph."""

    return {
        "nodes": {
            "detailer": {
                "class_type": UUID_WRAPPER,
                "inputs": {"image": ["source", 0], "steps": 12},
            },
        },
        "subgraphs": [
            {
                "id": UUID_WRAPPER,
                "name": "Detailer",
                "inputs": [
                    {
                        "name": "image",
                        "label": "Image",
                        "type": "IMAGE",
                        "localized_name": "Image",
                        "shape": 7,
                        "id": 101,
                    },
                    {"name": "steps", "label": "Steps", "type": "INT"},
                    {"name": "cfg", "label": "CFG"},
                ],
                "outputs": [
                    {"name": "IMAGE", "label": "Image", "type": "IMAGE"},
                    {"name": "MASK", "label": "Mask", "type": "MASK"},
                ],
                "nodes": [
                    {
                        "id": 1470,
                        "type": "DetailerForEach",
                        "widgets": [{"name": "internal_widget"}],
                        "widgets_values": [42],
                    }
                ],
            }
        ],
    }


def _metadata_runtime_graph(
    *,
    body_widget_values: list[object] | None = None,
    public_default: object | None = None,
) -> dict[str, object]:
    """Build an Automask-like wrapper graph with linked body definition metadata."""

    public_entry: dict[str, object] = {
        "name": "denoise",
        "label": "Denoise",
        "type": "FLOAT",
        "linkIds": [1041],
    }
    if public_default is not None:
        public_entry["default"] = public_default
    body_node: dict[str, object] = {
        "id": 1470,
        "type": "DetailerForEach",
        "inputs": [
            {"name": "image", "type": "IMAGE"},
            {
                "localized_name": "denoise",
                "name": "denoise",
                "type": "FLOAT",
                "widget": {"name": "denoise"},
                "link": 1041,
            },
        ],
    }
    if body_widget_values is not None:
        body_node["widgets_values"] = body_widget_values
    return {
        "nodes": {
            "detailer": {
                "class_type": UUID_WRAPPER,
                "inputs": {"image": ["source", 0]},
            },
        },
        "definitions": {
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
        },
        "subgraphs": [
            {
                "id": UUID_WRAPPER,
                "name": "Detailer",
                "inputNode": {"id": -10},
                "inputs": [
                    {
                        "name": "image",
                        "label": "Image",
                        "type": "IMAGE",
                        "linkIds": [1040],
                    },
                    public_entry,
                ],
                "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
                "links": {
                    "1040": {
                        "origin_id": -10,
                        "target_id": 1470,
                        "target_slot": 0,
                    },
                    "1041": {
                        "origin_id": -10,
                        "target_id": 1470,
                        "target_slot": 1,
                    },
                },
                "nodes": {"1470": body_node},
            }
        ],
    }


def _nested_metadata_runtime_graph() -> dict[str, object]:
    """Build a wrapper graph whose public field routes through a nested wrapper."""

    return {
        "nodes": {
            "detailer": {
                "class_type": UUID_WRAPPER,
                "inputs": {},
            },
        },
        "definitions": {
            "PrimitiveFloat": {
                "input": {
                    "required": {
                        "value": [
                            "FLOAT",
                            {
                                "default": 1.0,
                                "min": 0.25,
                                "max": 3.0,
                                "step": 0.05,
                            },
                        ]
                    }
                }
            }
        },
        "subgraphs": [
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
                    },
                ],
                "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
                "links": [
                    [1049, -10, 0, 1633, 0, "FLOAT"],
                ],
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
                    {
                        "name": "value",
                        "label": "Value",
                        "type": "FLOAT",
                        "linkIds": [1048],
                    },
                ],
                "outputs": [{"name": "SEGS", "label": "Segs", "type": "SEGS"}],
                "links": [
                    [1048, -10, 0, 1634, 0, "FLOAT"],
                ],
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
        ],
    }
