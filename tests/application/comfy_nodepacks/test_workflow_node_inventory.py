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

"""Tests for persisted workflow node dependency inventory."""

from substitute.domain.comfy_workflow.node_inventory import (
    PersistedNodepackHint,
    workflow_node_inventory,
)


def test_inventory_combines_ordinary_and_embedded_cube_nodes() -> None:
    """Ordinary and wild-Cube nodes should share one persisted inventory."""

    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "OrdinaryCustomNode",
                "title": "Ordinary node",
                "properties": {"cnr_id": "ordinary-pack", "ver": "1.2.0"},
            },
            {"id": 2, "type": "cube-definition"},
            {"id": 3, "type": "Note"},
        ],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "id": "cube-definition",
                    "nodes": [],
                    "extra": {
                        "sugarcubes_document": {
                            "cube_id": "local/example.cube",
                            "version": "1.0.0",
                            "metadata": {"default_alias": "Wild Example"},
                            "implementation": {
                                "nodes": {
                                    "detailer": {
                                        "class_type": "DetailerForEach",
                                        "label": "Detailer",
                                        "original_id": "source:42",
                                        "inputs": {},
                                    },
                                    "text": {
                                        "class_type": "PrimitiveStringMultiline",
                                        "label": "Prompt",
                                        "inputs": {"value": "hello"},
                                    },
                                    "local_wrapper": {
                                        "class_type": "local-detailer-wrapper",
                                        "label": "Embedded subgraph wrapper",
                                        "inputs": {},
                                    },
                                },
                                "subgraphs": [
                                    {
                                        "id": "local-detailer-wrapper",
                                        "nodes": [
                                            {
                                                "id": 42,
                                                "type": "DetailerForEach",
                                                "properties": {
                                                    "cnr_id": "comfyui-impact-pack",
                                                    "ver": "8.28.0",
                                                },
                                            }
                                        ],
                                    }
                                ],
                            },
                        }
                    },
                }
            ]
        },
    }

    inventory = workflow_node_inventory(workflow)

    ordinary = next(
        item for item in inventory if item.class_type == "OrdinaryCustomNode"
    )
    detailer = next(
        item
        for item in inventory
        if item.class_type == "DetailerForEach" and item.node_id == "source:42"
    )
    assert ordinary.cube_alias is None
    assert ordinary.title == "Ordinary node"
    assert ordinary.nodepack_hint == PersistedNodepackHint(
        registry_id="ordinary-pack",
        auxiliary_id=None,
        version="1.2.0",
    )
    assert detailer.cube_alias == "Wild Example"
    assert detailer.title == "Detailer"
    assert detailer.nodepack_hint == PersistedNodepackHint(
        registry_id="comfyui-impact-pack",
        auxiliary_id=None,
        version="8.28.0",
    )
    assert "cube-definition" not in {item.class_type for item in inventory}
    assert "local-detailer-wrapper" not in {item.class_type for item in inventory}
    assert "Note" not in {item.class_type for item in inventory}


def test_inventory_refuses_ambiguous_class_package_hints() -> None:
    """Conflicting saved package facts must not be guessed onto a node."""

    workflow = {
        "nodes": [{"id": 1, "type": "cube-definition"}],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "id": "cube-definition",
                    "extra": {
                        "sugarcubes_document": {
                            "cube_id": "local/example.cube",
                            "version": "1.0.0",
                            "implementation": {
                                "nodes": {
                                    "ambiguous": {
                                        "class_type": "SharedClass",
                                        "inputs": {},
                                    }
                                },
                                "subgraphs": [
                                    {
                                        "id": "one",
                                        "nodes": [
                                            {
                                                "id": 1,
                                                "type": "SharedClass",
                                                "properties": {"cnr_id": "pack-one"},
                                            },
                                            {
                                                "id": 2,
                                                "type": "SharedClass",
                                                "properties": {"cnr_id": "pack-two"},
                                            },
                                        ],
                                    }
                                ],
                            },
                        }
                    },
                }
            ]
        },
    }

    inventory = workflow_node_inventory(workflow)

    ambiguous = next(item for item in inventory if item.node_id == "ambiguous")
    assert ambiguous.nodepack_hint is None


def test_inventory_preserves_auxiliary_identity_without_promoting_it() -> None:
    """Legacy auxiliary package evidence should remain distinct from CNR identity."""

    workflow = {
        "nodes": [
            {
                "id": "legacy",
                "type": "LegacyNode",
                "properties": {"aux_id": "owner/repository", "ver": "abcdef"},
            }
        ],
        "links": [],
    }

    (item,) = workflow_node_inventory(workflow)

    assert item.nodepack_hint == PersistedNodepackHint(
        registry_id=None,
        auxiliary_id="owner/repository",
        version="abcdef",
    )
