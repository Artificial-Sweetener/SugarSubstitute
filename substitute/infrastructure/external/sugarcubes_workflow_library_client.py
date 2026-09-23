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

"""Adapt SugarCubes workflow classification and capture HTTP contracts."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from substitute.domain.common import JsonObject
from substitute.domain.cube_library import (
    WorkflowCubeAccess,
    WorkflowCubeCaptureResult,
    WorkflowCubeClassification,
    WorkflowCubeClassificationReport,
    WorkflowCubeLibraryClass,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import default_http_post

HttpPost = Callable[..., Any]


class SugarCubesWorkflowLibraryError(RuntimeError):
    """Report rejected or malformed workflow library operations."""


class SugarCubesWorkflowLibraryClient:
    """Read transient classifications and persist exact Captured Cubes."""

    def __init__(
        self,
        endpoint: ComfyEndpoint,
        *,
        http_post: HttpPost | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        """Capture one endpoint and bounded injectable transport."""

        self._endpoint = endpoint
        self._http_post = http_post or default_http_post
        self._timeout_seconds = timeout_seconds

    def classify(self, workflow: JsonObject) -> WorkflowCubeClassificationReport:
        """Classify embedded definitions without changing workflow content."""

        payload = self._post(
            self._endpoint.sugarcubes_workflow_cube_classification_url(),
            {"workflow": workflow},
            operation="classification",
        )
        return parse_workflow_cube_classification_report(payload)

    def capture(
        self,
        workflow: JsonObject,
        *,
        definition_id: str,
        expected_semantic_hash: str,
    ) -> WorkflowCubeCaptureResult:
        """Persist one exact embedded definition through SugarCubes."""

        payload = self._post(
            self._endpoint.sugarcubes_workflow_cube_capture_url(),
            {
                "workflow": workflow,
                "definition_id": definition_id,
                "expected_semantic_hash": expected_semantic_hash,
            },
            operation="capture",
        )
        item = _mapping(payload, "Cube capture")
        if item.get("schema_version") != 1:
            raise SugarCubesWorkflowLibraryError(
                "SugarCubes returned an unsupported Cube capture schema."
            )
        created = item.get("created")
        if not isinstance(created, bool):
            raise SugarCubesWorkflowLibraryError(
                "SugarCubes Cube capture creation state is invalid."
            )
        return WorkflowCubeCaptureResult(
            cube_id=_text(item, "cube_id"),
            cube_version=_text(item, "cube_version"),
            semantic_hash=_text(item, "semantic_hash"),
            created=created,
            classification=_classification(item.get("classification")),
        )

    def _post(
        self,
        url: str,
        body: Mapping[str, object],
        *,
        operation: str,
    ) -> object:
        """Post one bounded request and decode its JSON response."""

        response = self._http_post(url, json=body, timeout=self._timeout_seconds)
        status_code = getattr(response, "status_code", 200)
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise SugarCubesWorkflowLibraryError(
                f"SugarCubes returned an invalid workflow Cube {operation} response."
            ) from error
        if isinstance(status_code, int) and status_code >= 400:
            raise SugarCubesWorkflowLibraryError(_error_message(payload, operation))
        response.raise_for_status()
        return payload


def parse_workflow_cube_classification_report(
    value: object,
) -> WorkflowCubeClassificationReport:
    """Validate a workflow classification response at the network boundary."""

    payload = _mapping(value, "workflow Cube classification")
    if payload.get("schema_version") != 1:
        raise SugarCubesWorkflowLibraryError(
            "SugarCubes returned an unsupported workflow Cube classification schema."
        )
    definitions = _sequence(payload, "definitions")
    return WorkflowCubeClassificationReport(
        definitions=tuple(_classification(item) for item in definitions)
    )


def _classification(value: object) -> WorkflowCubeClassification:
    """Parse one embedded-definition classification."""

    item = _mapping(value, "Cube classification")
    try:
        primary_class = WorkflowCubeLibraryClass(_text(item, "primary_class"))
        access = WorkflowCubeAccess(_text(item, "access"))
    except ValueError as error:
        raise SugarCubesWorkflowLibraryError(
            "SugarCubes Cube classification enum is invalid."
        ) from error
    source_available = item.get("source_available")
    if not isinstance(source_available, bool):
        raise SugarCubesWorkflowLibraryError(
            "SugarCubes Cube source availability is invalid."
        )
    return WorkflowCubeClassification(
        definition_id=_text(item, "definition_id"),
        cube_id=_text(item, "cube_id"),
        cube_version=_text(item, "cube_version"),
        semantic_hash=_text(item, "semantic_hash"),
        instance_ids=_text_sequence(item, "instance_ids"),
        primary_class=primary_class,
        access=access,
        source_available=source_available,
        permitted_operations=frozenset(_text_sequence(item, "permitted_operations")),
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    """Require one string-keyed external object."""

    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise SugarCubesWorkflowLibraryError(f"SugarCubes {label} is invalid.")
    return value


def _sequence(value: Mapping[str, object], key: str) -> Sequence[object]:
    """Require one non-text external array."""

    result = value.get(key)
    if not isinstance(result, Sequence) or isinstance(result, (str, bytes)):
        raise SugarCubesWorkflowLibraryError(f"SugarCubes field '{key}' is invalid.")
    return result


def _text(value: Mapping[str, object], key: str) -> str:
    """Require one non-empty external string."""

    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise SugarCubesWorkflowLibraryError(f"SugarCubes field '{key}' is invalid.")
    return result.strip()


def _text_sequence(value: Mapping[str, object], key: str) -> tuple[str, ...]:
    """Require one external string array."""

    items = _sequence(value, key)
    if not all(isinstance(item, str) and item.strip() for item in items):
        raise SugarCubesWorkflowLibraryError(f"SugarCubes field '{key}' is invalid.")
    return tuple(item.strip() for item in items if isinstance(item, str))


def _error_message(payload: object, operation: str) -> str:
    """Read one structured SugarCubes rejection message."""

    if isinstance(payload, Mapping):
        error = payload.get("error")
        if isinstance(error, Mapping) and isinstance(error.get("message"), str):
            return str(error["message"])
    return f"SugarCubes rejected the workflow Cube {operation} request."


__all__ = [
    "SugarCubesWorkflowLibraryClient",
    "SugarCubesWorkflowLibraryError",
    "parse_workflow_cube_classification_report",
]
