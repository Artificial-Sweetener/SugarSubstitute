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

"""Verify typed SugarCubes workflow classification and capture transport."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.cube_library import WorkflowCubeLibraryClass
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.sugarcubes_workflow_library_client import (
    SugarCubesWorkflowLibraryClient,
)


def test_client_classifies_an_unsaved_wild_cube() -> None:
    """Preserve SugarCubes' read-only wild classification and capture permission."""

    transport = _Transport(_classification_payload(primary_class="none"))
    client = SugarCubesWorkflowLibraryClient(
        ComfyEndpoint("127.0.0.1", 8188),
        http_post=transport,
    )

    report = client.classify({"nodes": [], "links": []})

    assert transport.url.endswith("/sugarcubes/v2/cubes/classify-workflow")
    assert transport.body == {"workflow": {"nodes": [], "links": []}}
    classification = report.definitions[0]
    assert classification.primary_class is WorkflowCubeLibraryClass.NONE
    assert classification.can_capture is True


def test_client_captures_the_exact_embedded_definition() -> None:
    """Send stale-state protection and return refreshed Captured Cube state."""

    classification_payload = _classification_payload(primary_class="captured")
    definitions = classification_payload["definitions"]
    assert isinstance(definitions, list)
    classification = definitions[0]
    assert isinstance(classification, dict)
    transport = _Transport(
        {
            "schema_version": 1,
            "cube_id": "Example/Wild.cube",
            "cube_version": "1.0.0",
            "semantic_hash": "a" * 64,
            "created": True,
            "classification": classification,
        }
    )
    client = SugarCubesWorkflowLibraryClient(
        ComfyEndpoint("127.0.0.1", 8188),
        http_post=transport,
    )

    result = client.capture(
        {"nodes": [], "links": []},
        definition_id="definition-wild",
        expected_semantic_hash="a" * 64,
    )

    assert transport.url.endswith("/sugarcubes/v2/cubes/captured")
    assert transport.body == {
        "workflow": {"nodes": [], "links": []},
        "definition_id": "definition-wild",
        "expected_semantic_hash": "a" * 64,
    }
    assert result.created is True
    assert result.classification.primary_class is WorkflowCubeLibraryClass.CAPTURED
    assert result.classification.can_capture is False


def _classification_payload(*, primary_class: str) -> dict[str, object]:
    """Return one schema-one classification response."""

    operations = ["keep", "capture"] if primary_class == "none" else ["keep"]
    return {
        "schema_version": 1,
        "definitions": [
            {
                "definition_id": "definition-wild",
                "cube_id": "Example/Wild.cube",
                "cube_version": "1.0.0",
                "semantic_hash": "a" * 64,
                "instance_ids": ["instance-wild"],
                "primary_class": primary_class,
                "access": "read_only",
                "source_available": False,
                "permitted_operations": operations,
            }
        ],
    }


@dataclass
class _Response:
    """Return one injected JSON payload."""

    payload: object
    status_code: int = 200

    def json(self) -> object:
        """Return the configured payload."""

        return self.payload

    def raise_for_status(self) -> None:
        """Accept the response."""


class _Transport:
    """Capture one synchronous library request."""

    def __init__(self, payload: object) -> None:
        """Store one response payload."""

        self._payload = payload
        self.url = ""
        self.body: object = None

    def __call__(self, url: str, *, json: object, timeout: float) -> _Response:
        """Capture request details and return the injected response."""

        self.url = url
        self.body = json
        assert timeout == 10.0
        return _Response(self._payload)
