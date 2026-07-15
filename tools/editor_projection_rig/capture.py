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

"""Capture live editor projection fixtures from the running Substitute backend."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from substitute.domain.cubes import (
    SubgraphWrapperDefinitionIndex,
    materialize_cube_runtime_graph,
    validate_canonical_cube_document,
)

from .fixtures import stable_json_hash, workflow_fixture_path, write_json
from .scenarios import WorkflowScenario
from .signatures import signature_from_fixture


@dataclass(frozen=True, slots=True)
class CaptureEndpoint:
    """Identify the live backend endpoint used for fixture capture."""

    base_url: str = "http://127.0.0.1:8188"
    timeout_seconds: float = 10.0


def capture_scenarios(
    scenarios: Sequence[WorkflowScenario],
    *,
    output_dir: Path,
    endpoint: CaptureEndpoint,
) -> dict[str, Any]:
    """Capture all requested scenarios and return a capture manifest."""

    started_at = perf_counter()
    catalog = _get_json(endpoint, "/substitute/v1/cube-library/catalog")
    object_info = _get_json(endpoint, "/object_info")
    written: list[str] = []
    fixture_hashes: dict[str, str] = {}
    for scenario in scenarios:
        fixture = _capture_workflow_fixture(
            scenario,
            catalog=catalog,
            object_info=object_info,
            endpoint=endpoint,
        )
        path = workflow_fixture_path(output_dir, scenario.workflow_id)
        write_json(path, fixture)
        written.append(str(path))
        fixture_hashes[scenario.workflow_id] = stable_json_hash(fixture)
    manifest = {
        "schema_version": 1,
        "captured_at": _utc_now(),
        "endpoint": endpoint.base_url,
        "scenario_ids": [scenario.workflow_id for scenario in scenarios],
        "fixture_hashes": fixture_hashes,
        "elapsed_ms": round((perf_counter() - started_at) * 1000.0, 3),
        "written": written,
    }
    write_json(output_dir / "capture_manifest.json", manifest)
    return manifest


def _capture_workflow_fixture(
    scenario: WorkflowScenario,
    *,
    catalog: Mapping[str, Any],
    object_info: Mapping[str, Any],
    endpoint: CaptureEndpoint,
) -> dict[str, Any]:
    """Capture one workflow fixture from live catalog and cube artifacts."""

    resolved_cubes: list[dict[str, Any]] = []
    used_node_classes: set[str] = set()
    for index, requested_label in enumerate(scenario.requested_cube_labels, start=1):
        catalog_entry = _resolve_catalog_entry(catalog, requested_label)
        cube_id = str(catalog_entry["cubeId"])
        version = str(catalog_entry["version"])
        artifact = _get_json(
            endpoint,
            "/substitute/v1/cube-library/cubes/load?"
            f"cubeId={quote(cube_id, safe='')}&version={quote(version, safe='')}",
        )
        cube_buffer = _required_mapping(artifact.get("cube"), "cube")
        used_node_classes.update(_node_classes(cube_buffer))
        used_node_classes.update(_body_node_classes(cube_buffer))
        resolved_cubes.append(
            {
                "alias": f"Cube {index}: {catalog_entry.get('displayName', cube_id)}",
                "requested_label": requested_label,
                "cube_id": cube_id,
                "version": version,
                "display_name": str(catalog_entry.get("displayName", "")),
                "content_hash": str(catalog_entry.get("contentHash", "")),
                "catalog_entry": dict(catalog_entry),
                "cube_buffer": dict(cube_buffer),
                "artifact": dict(artifact),
            }
        )
    node_definitions = {
        node_class: object_info[node_class]
        for node_class in sorted(used_node_classes)
        if node_class in object_info
    }
    fixture = {
        "schema_version": 1,
        "workflow_id": scenario.workflow_id,
        "requested_cube_labels": list(scenario.requested_cube_labels),
        "capture_timestamp": _utc_now(),
        "endpoint": endpoint.base_url,
        "stack_order": [cube["alias"] for cube in resolved_cubes],
        "global_overrides": {},
        "global_override_selections": {},
        "cubes": resolved_cubes,
        "node_definitions": node_definitions,
    }
    fixture["settled_signature"] = signature_from_fixture(fixture).to_json()
    fixture["fixture_hash"] = stable_json_hash(fixture)
    return fixture


def _resolve_catalog_entry(
    catalog: Mapping[str, Any],
    requested_label: str,
) -> Mapping[str, Any]:
    """Resolve a requested scenario label against the live cube catalog."""

    cubes = catalog.get("cubes", [])
    normalized = requested_label.casefold()
    if not isinstance(cubes, list):
        message = "Cube catalog did not contain a cubes list."
        raise ValueError(message)
    for entry in cubes:
        if not isinstance(entry, Mapping):
            continue
        display_name = str(entry.get("displayName", ""))
        cube_id = str(entry.get("cubeId", ""))
        if normalized in {display_name.casefold(), cube_id.casefold()}:
            return entry
    message = f"Could not resolve required cube label {requested_label!r}."
    raise ValueError(message)


def _node_classes(cube_buffer: Mapping[str, Any]) -> set[str]:
    """Return all node class names referenced by one cube buffer."""

    implementation = _required_mapping(
        cube_buffer.get("implementation"), "implementation"
    )
    nodes = _required_mapping(implementation.get("nodes"), "nodes")
    return {
        str(node_data.get("class_type", ""))
        for node_data in nodes.values()
        if isinstance(node_data, Mapping) and node_data.get("class_type")
    }


def _body_node_classes(cube_buffer: Mapping[str, Any]) -> set[str]:
    """Return hidden subgraph body classes needed for wrapper field metadata."""

    document = validate_canonical_cube_document(cube_buffer)
    runtime_graph = materialize_cube_runtime_graph(document)
    wrapper_index = SubgraphWrapperDefinitionIndex.from_runtime_graph(runtime_graph)
    return set(wrapper_index.body_node_classes())


def _get_json(endpoint: CaptureEndpoint, path: str) -> dict[str, Any]:
    """Fetch one JSON object from the live backend endpoint."""

    request = Request(endpoint.base_url.rstrip("/") + path, method="GET")
    with urlopen(request, timeout=endpoint.timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        message = f"Endpoint {path} returned non-object JSON."
        raise ValueError(message)
    return payload


def _required_mapping(value: object, label: str) -> Mapping[str, Any]:
    """Return a required mapping value or raise a diagnostic error."""

    if isinstance(value, Mapping):
        return value
    message = f"Expected mapping for {label}."
    raise ValueError(message)


def _utc_now() -> str:
    """Return the current UTC timestamp for fixture metadata."""

    return datetime.now(UTC).isoformat(timespec="seconds")
