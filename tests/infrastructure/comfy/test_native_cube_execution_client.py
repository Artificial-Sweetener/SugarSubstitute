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

"""Verify negotiated native Cube graph dispatch to SugarCubes."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.ports import ListenerOutputSource, QueueVisualRunContext
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.native_cube_execution_client import (
    NativeCubeExecutionClient,
)


@dataclass
class _Response:
    """Provide the requests response surface consumed by the client."""

    payload: object
    status_code: int = 200

    def raise_for_status(self) -> None:
        """Raise only for explicit error fixtures."""

        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> object:
        """Return the configured JSON payload."""

        return self.payload


class _Http:
    """Capture capability and execution requests without network access."""

    def __init__(
        self,
        capabilities: object,
        *,
        backend_capabilities: object | None = None,
        queue_response: _Response | None = None,
    ) -> None:
        """Store capability response and initialize call capture."""

        self.capabilities = capabilities
        self.backend_capabilities = backend_capabilities or _backend_capabilities()
        self.queue_response = queue_response
        self.posts: list[tuple[str, object]] = []

    def get(self, _url: str, *, timeout: float) -> _Response:
        """Return the configured capabilities."""

        assert timeout > 0
        if _url.endswith("/substitute/v1/capabilities"):
            return _Response(self.backend_capabilities)
        return _Response(self.capabilities)

    def post(self, url: str, *, json: object, timeout: float) -> _Response:
        """Capture one native queue body and accept it."""

        assert timeout > 0
        self.posts.append((url, json))
        if self.queue_response is not None:
            return self.queue_response
        return _Response(
            {
                "accepted": True,
                "prompt_id": "native-prompt",
                "number": 1.0,
                "execution_prompt": {
                    "cube-a:sampler": {
                        "class_type": "KSampler",
                        "inputs": {"steps": 20},
                    }
                },
                "report": {
                    "execution_owner": "sugarcubes",
                    "execution_node_identities": [
                        {
                            "execution_id": "cube-a:sampler",
                            "instance_id": "cube-a",
                            "instance_alias": "First Cube",
                        }
                    ],
                    "output_identities": [
                        {
                            "execution_id": "__sugarcubes_cube_output__:cube-a:0",
                            "instance_id": "cube-a",
                            "instance_alias": "First Cube",
                        }
                    ],
                },
            }
        )


def test_client_uses_friendly_cube_names_for_visual_source_labels() -> None:
    """Keep model qualification in metadata instead of Output canvas tab names."""

    http = _Http(
        _capabilities(),
        queue_response=_Response(
            {
                "prompt_id": "native-prompt",
                "report": {
                    "execution_node_identities": [
                        {
                            "execution_id": "sampler",
                            "instance_id": "cube-a",
                            "instance_alias": "Anima/Prompt by Region",
                        }
                    ],
                    "output_identities": [
                        {
                            "execution_id": "output",
                            "instance_id": "cube-a",
                            "instance_alias": "Anima/Prompt by Region",
                        }
                    ],
                },
            }
        ),
    )

    result = _client(http).queue(
        workflow={"nodes": []},
        client_id="client-1",
        visual_context=_context(),
    )

    assert result.output_sources[0].source_label == "Prompt by Region"
    assert result.execution_sources[0].source_label == "Prompt by Region"


def test_client_negotiates_and_queues_canonical_workflow_with_context() -> None:
    """Native dispatch should speak SugarCubes graph and BackEnd context contracts."""

    http = _Http(_capabilities())
    client = NativeCubeExecutionClient(
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        http=http,
    )
    context = QueueVisualRunContext(
        workflow_id="wf-1",
        generation_run_id="run-1",
        client_id="client-1",
        sources={},
    )
    workflow = {"version": 0.4, "nodes": [], "links": []}

    result = client.queue(
        workflow=workflow,
        client_id="client-1",
        visual_context=context,
        preview_method="latent2rgb",
        persistence_sugar_script="# Project: Test",
    )

    assert result.prompt_id == "native-prompt"
    assert result.output_sources == (
        ListenerOutputSource(
            node_id="__sugarcubes_cube_output__:cube-a:0",
            source_key="cube:cube-a",
            source_label="First Cube",
        ),
    )
    assert result.execution_prompt == {
        "cube-a:sampler": {"class_type": "KSampler", "inputs": {"steps": 20}}
    }
    assert result.execution_sources == (
        ListenerOutputSource(
            node_id="cube-a:sampler",
            source_key="cube:cube-a",
            source_label="First Cube",
        ),
    )
    assert len(http.posts) == 1
    url, body = http.posts[0]
    assert url.endswith("/sugarcubes/v2/executions/queue")
    assert isinstance(body, dict)
    assert body["workflow"] is workflow
    assert body["queue"] == {"client_id": "client-1", "atomic": True}
    extra = body["extra_data"]
    assert isinstance(extra, dict)
    assert extra["substitute"] == {
        "schemaVersion": 1,
        "workflowId": "wf-1",
        "generationRunId": "run-1",
        "clientId": "client-1",
    }
    assert extra["extra_pnginfo"] == {
        "workflow": workflow,
        "sugar_script": "# Project: Test",
    }


def test_client_rejects_incompatible_native_execution_capabilities() -> None:
    """Generate must fail before queueing when the native contract is incompatible."""

    http = _Http({"available": True, "schema_version": 99})
    client = NativeCubeExecutionClient(
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        http=http,
    )

    result = client.queue(
        workflow={"nodes": []},
        client_id="client-1",
        visual_context=QueueVisualRunContext(
            workflow_id="wf-1",
            generation_run_id="run-1",
            client_id="client-1",
            sources={},
        ),
    )

    assert result.prompt_id is None
    assert result.error == "SugarCubes native execution contract is incompatible."
    assert http.posts == []


def test_client_rejects_incompatible_backend_context_bridge() -> None:
    """Generate must fail before queueing when outputs could be orphaned."""

    http = _Http(_capabilities(), backend_capabilities={"features": []})
    result = _client(http).queue(
        workflow={"nodes": []},
        client_id="client-1",
        visual_context=_context(),
    )

    assert result.prompt_id is None
    assert result.error == (
        "Substitute BackEnd native queue context bridge is incompatible."
    )
    assert http.posts == []


def test_client_surfaces_native_graph_rejection() -> None:
    """Return SugarCubes validation detail without inventing a prompt identity."""

    http = _Http(
        _capabilities(),
        queue_response=_Response(
            {"error": {"message": "Cube graph contains a cycle."}},
            status_code=422,
        ),
    )
    result = _client(http).queue(
        workflow={"nodes": []},
        client_id="client-1",
        visual_context=_context(),
    )

    assert result.prompt_id is None
    assert result.error == "Cube graph contains a cycle."


def test_client_rejects_malformed_success_response() -> None:
    """Treat a success response without a prompt id as a queue failure."""

    http = _Http(_capabilities(), queue_response=_Response({"accepted": True}))
    result = _client(http).queue(
        workflow={"nodes": []},
        client_id="client-1",
        visual_context=_context(),
    )

    assert result.prompt_id is None
    assert result.error == "SugarCubes queue response did not include a prompt id."


def test_client_ignores_malformed_or_duplicate_output_identities() -> None:
    """Only complete unique report identities should enter output recovery."""

    http = _Http(
        _capabilities(),
        queue_response=_Response(
            {
                "prompt_id": "native-prompt",
                "report": {
                    "output_identities": [
                        {
                            "execution_id": "output-1",
                            "instance_id": "cube-a",
                            "instance_alias": " ",
                        },
                        {
                            "execution_id": "output-1",
                            "instance_id": "cube-b",
                            "instance_alias": "Duplicate",
                        },
                        {"execution_id": "output-2"},
                        "invalid",
                    ]
                },
            }
        ),
    )

    result = _client(http).queue(
        workflow={"nodes": []},
        client_id="client-1",
        visual_context=_context(),
    )

    assert result.output_sources == (
        ListenerOutputSource(
            node_id="output-1",
            source_key="cube:cube-a",
            source_label="cube-a",
        ),
    )


def test_client_rejects_malformed_execution_prompt_without_failing_queue() -> None:
    """Listener metadata should fall back safely when a prompt snapshot is malformed."""

    http = _Http(
        _capabilities(),
        queue_response=_Response(
            {
                "prompt_id": "native-prompt",
                "execution_prompt": {"node-1": "invalid"},
            }
        ),
    )

    result = _client(http).queue(
        workflow={"nodes": []},
        client_id="client-1",
        visual_context=_context(),
    )

    assert result.prompt_id == "native-prompt"
    assert result.execution_prompt is None


def _client(http: _Http) -> NativeCubeExecutionClient:
    """Build one client with the supplied deterministic transport."""

    return NativeCubeExecutionClient(
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        http=http,
    )


def _context() -> QueueVisualRunContext:
    """Return one valid empty-source Substitute routing context."""

    return QueueVisualRunContext(
        workflow_id="wf-1",
        generation_run_id="run-1",
        client_id="client-1",
        sources={},
    )


def _capabilities() -> dict[str, object]:
    """Return the exact native execution capability tuple supported by Substitute."""

    return {
        "available": True,
        "schema_version": 1,
        "workflow_schema_version": 1,
        "report_schema_version": 1,
        "queue_observer_api_version": 1,
        "queue_route": "/sugarcubes/v2/executions/queue",
        "execution_owner": "sugarcubes",
        "atomic_queueing": True,
        "cube_scoped_optimization": True,
        "validated_queue_observers": True,
    }


def _backend_capabilities() -> dict[str, object]:
    """Return the BackEnd native context bridge contract."""

    return {
        "features": ["native-cube-queue-context"],
        "nativeCubeQueueContext": {
            "schemaVersion": 1,
            "queueObserverApiVersion": 1,
            "requiredObserver": True,
            "preQueuePersistence": True,
            "sourceIdentityFromExecutionReport": True,
        },
    }
