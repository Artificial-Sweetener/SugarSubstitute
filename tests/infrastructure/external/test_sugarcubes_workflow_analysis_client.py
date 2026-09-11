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

"""Verify typed SugarCubes canonical graph analysis transport."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.common import JsonObject
from substitute.domain.comfy_workflow.cube_analysis import CubeGraphEdgeOrigin
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.sugarcubes_workflow_analysis_client import (
    SugarCubesWorkflowAnalysisClient,
)


def test_client_parses_one_bounded_analysis_response() -> None:
    """Keep dynamic SugarCubes JSON out of workflow domain consumers."""

    transport = _Transport()
    client = SugarCubesWorkflowAnalysisClient(
        ComfyEndpoint("127.0.0.1", 8188), http_post=transport
    )

    analysis = client.analyze({"nodes": [], "links": []})

    assert transport.url.endswith("/sugarcubes/v2/workflows/analyze")
    assert transport.body == {
        "schema_version": 1,
        "workflow": {"nodes": [], "links": []},
    }
    assert analysis.workflow_semantic_hash == "semantic"
    assert analysis.instances[0].instance_id == "cube-a"
    assert analysis.edges[0].origin is CubeGraphEdgeOrigin.PROXIMITY
    assert analysis.segments[0].instance_ids == ("cube-a", "cube-b")
    assert analysis.workflow == {
        "nodes": [],
        "links": [],
        "extra": {"kept": True},
    }


def test_client_requests_one_atomic_sugarcubes_reorder() -> None:
    """Send the complete graph and one exact segment permutation."""

    transport = _Transport()
    client = SugarCubesWorkflowAnalysisClient(
        ComfyEndpoint("127.0.0.1", 8188), http_post=transport
    )

    analysis = client.reorder(
        {"nodes": [], "links": []},
        segment_instance_ids=("cube-a", "cube-b"),
        ordered_instance_ids=("cube-b", "cube-a"),
    )

    assert transport.url.endswith("/sugarcubes/v2/workflows/reorder")
    assert transport.body == {
        "schema_version": 1,
        "workflow": {"nodes": [], "links": []},
        "segment_instance_ids": ["cube-a", "cube-b"],
        "ordered_instance_ids": ["cube-b", "cube-a"],
    }
    assert analysis.workflow_semantic_hash == "semantic"


def test_client_requests_sugarcubes_owned_cube_append_and_remove() -> None:
    """Keep Cube graph structure mutation behind SugarCubes' versioned boundary."""

    transport = _Transport()
    client = SugarCubesWorkflowAnalysisClient(
        ComfyEndpoint("127.0.0.1", 8188), http_post=transport
    )
    document: JsonObject = {
        "cube_id": "Artificial-Sweetener/Test/A.cube",
        "version": "1.0.0",
        "implementation": {"nodes": {}, "inputs": {}, "outputs": {}},
    }

    client.append_cube(
        {"nodes": [], "links": []},
        instance_id="cube-a",
        alias="A",
        bypassed=True,
        document=document,
    )

    assert transport.url.endswith("/sugarcubes/v2/workflows/cubes/append")
    assert transport.body == {
        "schema_version": 1,
        "workflow": {"nodes": [], "links": []},
        "cube": {
            "instance_id": "cube-a",
            "alias": "A",
            "bypassed": True,
            "document": document,
        },
    }

    client.remove_cube(
        {"nodes": [], "links": []},
        instance_id="cube-a",
    )

    assert transport.url.endswith("/sugarcubes/v2/workflows/cubes/remove")
    assert transport.body == {
        "schema_version": 1,
        "workflow": {"nodes": [], "links": []},
        "instance_id": "cube-a",
    }


def test_client_creates_one_native_graph_from_an_ordered_legacy_stack() -> None:
    """Send every migrated Cube in one bounded SugarCubes request."""

    transport = _Transport()
    client = SugarCubesWorkflowAnalysisClient(
        ComfyEndpoint("127.0.0.1", 8188), http_post=transport
    )
    cubes = [
        {
            "instance_id": "cube-a",
            "alias": "A",
            "bypassed": False,
            "document": {
                "cube_id": "Artificial-Sweetener/Test/A.cube",
                "version": "1.0.0",
                "implementation": {"nodes": {}, "inputs": {}, "outputs": {}},
            },
        }
    ]

    client.create_cube_workflow(cubes)

    assert transport.url.endswith("/sugarcubes/v2/workflows/cubes/create")
    assert transport.body == {"schema_version": 1, "cubes": cubes}


@dataclass
class _Response:
    """Return one stable successful analysis payload."""

    status_code: int = 200

    def json(self) -> object:
        """Return a complete schema-one response."""

        return {
            "schema_version": 1,
            "workflow_semantic_hash": "semantic",
            "instances": [
                {
                    "instance_id": "cube-a",
                    "node_id": "1",
                    "definition_id": "definition-a",
                    "cube_id": "Artificial-Sweetener/Test/A.cube",
                    "cube_version": "1.0.0",
                    "instance_alias": "A",
                    "execution_mode": 0,
                }
            ],
            "edges": [
                {
                    "source_instance_id": "cube-a",
                    "source_binding": "output.image",
                    "target_instance_id": "cube-b",
                    "target_binding": "input.image",
                    "origin": "proximity",
                }
            ],
            "proximity_connections": [
                {
                    "source_instance_id": "cube-a",
                    "source_binding": "output.image",
                    "target_instance_id": "cube-b",
                    "target_binding": "input.image",
                }
            ],
            "segments": [
                {
                    "instance_ids": ["cube-a", "cube-b"],
                    "reorderable": True,
                    "boundary_node_ids": [],
                }
            ],
            "workflow": {
                "nodes": [],
                "links": [],
                "extra": {"kept": True},
            },
        }

    def raise_for_status(self) -> None:
        """Accept the response."""


class _Transport:
    """Capture one synchronous HTTP request."""

    def __init__(self) -> None:
        """Initialize request capture state."""

        self.url = ""
        self.body: object = None

    def __call__(self, url: str, *, json: object, timeout: float) -> _Response:
        """Capture the request and return a stable response."""

        self.url = url
        self.body = json
        assert timeout == 10.0
        return _Response()
