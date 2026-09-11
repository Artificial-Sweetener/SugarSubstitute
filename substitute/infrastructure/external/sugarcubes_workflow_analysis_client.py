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

"""Read SugarCubes-owned workflow projections through its versioned API."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from typing import Any

from substitute.domain.comfy_workflow.cube_analysis import (
    AnalyzedCubeEdge,
    AnalyzedCubeInstance,
    AnalyzedCubeSegment,
    CanonicalCubeGraphAnalysis,
    CubeGraphEdgeOrigin,
)
from substitute.domain.common import JsonObject
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import default_http_post

HttpPost = Callable[..., Any]


class SugarCubesWorkflowAnalysisError(RuntimeError):
    """Report a rejected or malformed canonical graph analysis response."""


class SugarCubesWorkflowAnalysisClient:
    """Adapt SugarCubes graph analysis to typed Substitute domain values."""

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

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Return one complete SugarCubes projection for a canonical graph."""

        return self._post_analysis(
            self._endpoint.sugarcubes_workflow_analysis_url(),
            {"schema_version": 1, "workflow": workflow},
            operation="analysis",
        )

    def reorder(
        self,
        workflow: JsonObject,
        *,
        segment_instance_ids: Sequence[str],
        ordered_instance_ids: Sequence[str],
    ) -> CanonicalCubeGraphAnalysis:
        """Return one graph atomically reordered by SugarCubes."""

        return self._post_analysis(
            self._endpoint.sugarcubes_workflow_reorder_url(),
            {
                "schema_version": 1,
                "workflow": workflow,
                "segment_instance_ids": list(segment_instance_ids),
                "ordered_instance_ids": list(ordered_instance_ids),
            },
            operation="mutation",
        )

    def append_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
        alias: str,
        bypassed: bool,
        document: JsonObject,
    ) -> CanonicalCubeGraphAnalysis:
        """Return the graph after SugarCubes appends one exact Cube document."""

        return self._post_analysis(
            self._endpoint.sugarcubes_workflow_cube_append_url(),
            {
                "schema_version": 1,
                "workflow": workflow,
                "cube": {
                    "instance_id": instance_id,
                    "alias": alias,
                    "bypassed": bypassed,
                    "document": document,
                },
            },
            operation="mutation",
        )

    def create_cube_workflow(
        self,
        cubes: Sequence[Mapping[str, object]],
    ) -> CanonicalCubeGraphAnalysis:
        """Return one native graph created from an ordered legacy Cube stack."""

        return self._post_analysis(
            self._endpoint.sugarcubes_workflow_cube_create_url(),
            {
                "schema_version": 1,
                "cubes": [deepcopy(dict(cube)) for cube in cubes],
            },
            operation="migration",
        )

    def remove_cube(
        self,
        workflow: JsonObject,
        *,
        instance_id: str,
    ) -> CanonicalCubeGraphAnalysis:
        """Return the graph after SugarCubes removes one recognized Cube."""

        return self._post_analysis(
            self._endpoint.sugarcubes_workflow_cube_remove_url(),
            {
                "schema_version": 1,
                "workflow": workflow,
                "instance_id": instance_id,
            },
            operation="mutation",
        )

    def _post_analysis(
        self,
        url: str,
        body: Mapping[str, object],
        *,
        operation: str,
    ) -> CanonicalCubeGraphAnalysis:
        """Post one bounded request and validate the shared analysis response."""

        response = self._http_post(
            url,
            json=body,
            timeout=self._timeout_seconds,
        )
        status_code = getattr(response, "status_code", 200)
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise SugarCubesWorkflowAnalysisError(
                f"SugarCubes returned an invalid workflow {operation} response."
            ) from error
        if isinstance(status_code, int) and status_code >= 400:
            raise SugarCubesWorkflowAnalysisError(_error_message(payload))
        response.raise_for_status()
        return parse_sugarcubes_workflow_analysis(payload)


def parse_sugarcubes_workflow_analysis(value: object) -> CanonicalCubeGraphAnalysis:
    """Validate dynamic JSON before it enters the workflow domain."""

    payload = _mapping(value, "workflow analysis")
    if payload.get("schema_version") != 1:
        raise SugarCubesWorkflowAnalysisError(
            "SugarCubes returned an unsupported workflow analysis schema."
        )
    return CanonicalCubeGraphAnalysis(
        workflow_semantic_hash=_text(payload, "workflow_semantic_hash"),
        instances=tuple(_instance(item) for item in _sequence(payload, "instances")),
        edges=tuple(_edge(item) for item in _sequence(payload, "edges")),
        proximity_edges=tuple(
            _edge(item, default_origin=CubeGraphEdgeOrigin.PROXIMITY)
            for item in _sequence(payload, "proximity_connections")
        ),
        segments=tuple(_segment(item) for item in _sequence(payload, "segments")),
        workflow=deepcopy(
            dict(_mapping(payload.get("workflow"), "normalized workflow"))
        ),
    )


def _instance(value: object) -> AnalyzedCubeInstance:
    """Parse one analyzed Cube identity."""

    item = _mapping(value, "Cube instance")
    execution_mode = item.get("execution_mode")
    if isinstance(execution_mode, bool) or not isinstance(execution_mode, int):
        raise SugarCubesWorkflowAnalysisError("Cube execution mode must be an integer.")
    return AnalyzedCubeInstance(
        instance_id=_text(item, "instance_id"),
        node_id=_text(item, "node_id"),
        definition_id=_text(item, "definition_id"),
        cube_id=_text(item, "cube_id"),
        cube_version=_text(item, "cube_version"),
        alias=_text(item, "instance_alias"),
        execution_mode=execution_mode,
    )


def _edge(
    value: object,
    *,
    default_origin: CubeGraphEdgeOrigin | None = None,
) -> AnalyzedCubeEdge:
    """Parse one explicit or proximity Cube boundary edge."""

    item = _mapping(value, "Cube edge")
    origin_value = item.get("origin")
    try:
        origin = (
            CubeGraphEdgeOrigin(origin_value)
            if isinstance(origin_value, str)
            else default_origin
        )
    except ValueError as error:
        raise SugarCubesWorkflowAnalysisError("Cube edge origin is invalid.") from error
    if origin is None:
        raise SugarCubesWorkflowAnalysisError("Cube edge origin is missing.")
    return AnalyzedCubeEdge(
        source_instance_id=_text(item, "source_instance_id"),
        source_binding=_text(item, "source_binding"),
        target_instance_id=_text(item, "target_instance_id"),
        target_binding=_text(item, "target_binding"),
        origin=origin,
    )


def _segment(value: object) -> AnalyzedCubeSegment:
    """Parse one stack projection segment."""

    item = _mapping(value, "Cube segment")
    reorderable = item.get("reorderable")
    if not isinstance(reorderable, bool):
        raise SugarCubesWorkflowAnalysisError("Cube segment reorder policy is invalid.")
    return AnalyzedCubeSegment(
        instance_ids=_text_sequence(item, "instance_ids"),
        reorderable=reorderable,
        boundary_node_ids=_text_sequence(item, "boundary_node_ids"),
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    """Require one string-keyed external object."""

    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise SugarCubesWorkflowAnalysisError(f"SugarCubes {label} is invalid.")
    return value


def _sequence(value: Mapping[str, object], key: str) -> Sequence[object]:
    """Require one non-text external array."""

    result = value.get(key)
    if not isinstance(result, Sequence) or isinstance(result, (str, bytes)):
        raise SugarCubesWorkflowAnalysisError(f"SugarCubes field '{key}' is invalid.")
    return result


def _text(value: Mapping[str, object], key: str) -> str:
    """Require one non-empty external string."""

    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise SugarCubesWorkflowAnalysisError(f"SugarCubes field '{key}' is invalid.")
    return result.strip()


def _text_sequence(value: Mapping[str, object], key: str) -> tuple[str, ...]:
    """Require one external string array."""

    items = _sequence(value, key)
    if not all(isinstance(item, str) and item.strip() for item in items):
        raise SugarCubesWorkflowAnalysisError(f"SugarCubes field '{key}' is invalid.")
    return tuple(item.strip() for item in items if isinstance(item, str))


def _error_message(payload: object) -> str:
    """Read one structured SugarCubes rejection message."""

    if isinstance(payload, Mapping):
        error = payload.get("error")
        if isinstance(error, Mapping) and isinstance(error.get("message"), str):
            return str(error["message"])
    return "SugarCubes rejected the workflow analysis request."


__all__ = [
    "SugarCubesWorkflowAnalysisClient",
    "SugarCubesWorkflowAnalysisError",
    "parse_sugarcubes_workflow_analysis",
]
