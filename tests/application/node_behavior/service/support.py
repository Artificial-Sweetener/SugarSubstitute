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

"""Provide typed wrapper and model fixtures for behavior-service tests."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.model_metadata import ModelCatalogItem
from substitute.application.node_behavior import ModelBackedNodeDetector
from tests.support.node_behavior import DummyNodeDefinitionGateway

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


__all__ = [
    "UUID_NESTED_WRAPPER",
    "UUID_WRAPPER",
    "RecordingNodeDefinitionGateway",
    "RequiredOnlyNodeDefinitionGateway",
    "_model_detector",
    "_model_item",
    "_nested_wrapper_definitions",
    "_nested_wrapper_live_definitions",
    "_nested_wrapper_subgraphs",
    "_wrapper_definitions",
    "_wrapper_live_definitions",
    "_wrapper_nodes",
    "_wrapper_subgraphs",
]
