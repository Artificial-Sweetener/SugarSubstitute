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

"""Validate authoritative bundled-workflow discovery and source accounting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.bundled_comfy_workflow_catalog import (
    SourceNodeDisposition,
    inventory_source_workflow,
    load_bundled_workflow_catalog,
)


def _write_json(path: Path, payload: object) -> None:
    """Write one deterministic JSON fixture beneath a temporary test root."""

    path.write_text(json.dumps(payload), encoding="utf-8")


def test_catalog_uses_nested_index_entries_as_the_authoritative_boundary(
    tmp_path: Path,
) -> None:
    """Catalog discovery should ignore non-index JSON and preserve UI categories."""

    _write_json(
        tmp_path / "index.json",
        [
            {
                "title": "Image",
                "templates": [
                    {"name": "first", "title": "First workflow"},
                    {"name": "second", "title": "Second workflow"},
                ],
            }
        ],
    )
    _write_json(tmp_path / "first.json", {"nodes": [], "links": []})
    _write_json(tmp_path / "second.json", {"nodes": [], "links": []})
    _write_json(tmp_path / "index.fr.json", [])
    _write_json(tmp_path / "fuse_options.json", {"threshold": 0.2})

    catalog = load_bundled_workflow_catalog(tmp_path)

    assert [(entry.name, entry.title, entry.category) for entry in catalog.entries] == [
        ("first", "First workflow", "Image"),
        ("second", "Second workflow", "Image"),
    ]
    assert len(catalog.fingerprint) == 64


def test_catalog_rejects_duplicate_and_missing_workflow_entries(tmp_path: Path) -> None:
    """Malformed catalog boundaries should fail before partial validation runs."""

    _write_json(
        tmp_path / "index.json",
        [
            {
                "title": "Image",
                "templates": [
                    {"name": "missing", "title": "Missing"},
                    {"name": "missing", "title": "Duplicate"},
                ],
            }
        ],
    )

    with pytest.raises(ValueError, match="missing"):
        load_bundled_workflow_catalog(tmp_path)


def test_source_inventory_expands_nested_subgraphs_and_classifies_frontend_nodes() -> (
    None
):
    """Independent traversal should match converter namespace and exclusion semantics."""

    inner_id = "inner-subgraph"
    outer_id = "outer-subgraph"
    workflow = {
        "nodes": [
            {"id": 1, "type": outer_id, "title": "Outer instance"},
            {"id": 2, "type": "MarkdownNote"},
            {"id": 3, "type": "Reroute"},
            {"id": 4, "type": "KSampler"},
        ],
        "definitions": {
            "subgraphs": [
                {
                    "id": outer_id,
                    "nodes": [
                        {"id": 10, "type": inner_id},
                        {"id": 11, "type": "PrimitiveNode"},
                    ],
                },
                {
                    "id": inner_id,
                    "nodes": [
                        {"id": 20, "type": "CLIPTextEncode"},
                        {"id": 21, "type": "Note"},
                    ],
                },
            ]
        },
    }

    inventory = inventory_source_workflow(workflow)
    by_id = {node.node_id: node for node in inventory.nodes}

    assert by_id["1"].disposition is SourceNodeDisposition.SUBGRAPH_INSTANCE
    assert by_id["1:10"].disposition is SourceNodeDisposition.SUBGRAPH_INSTANCE
    assert by_id["1:10:20"].disposition is SourceNodeDisposition.PROJECTED
    assert by_id["1:10:21"].disposition is SourceNodeDisposition.ANNOTATION
    assert by_id["1:11"].disposition is SourceNodeDisposition.PROJECTED
    assert by_id["2"].disposition is SourceNodeDisposition.ANNOTATION
    assert by_id["3"].disposition is SourceNodeDisposition.ROUTING
    assert by_id["4"].disposition is SourceNodeDisposition.PROJECTED
    assert {node.node_id for node in inventory.projected_nodes} == {
        "1:10:20",
        "1:11",
        "4",
    }
