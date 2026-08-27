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

"""Validate canonical cube contracts against input-asset semantics."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_asset_field_policy import (
    InputAssetFieldPolicy,
)
from substitute.application.workflows.workflow_graph_topology import (
    WorkflowGraphTopology,
)
from substitute.application.workflows.workflow_node_definition_service import (
    graph_nodes,
    node_class_type,
)

_ASSET_OUTPUT_TYPES = frozenset({"IMAGE", "MASK"})


@dataclass(frozen=True, slots=True)
class CubeInputAssetDiagnostic:
    """Describe one invalid input-asset contract in a cube artifact."""

    path: Path
    message: str


def validate_cube_root(cube_root: Path) -> tuple[CubeInputAssetDiagnostic, ...]:
    """Validate every cube below a repository or catalog root."""

    diagnostics: list[CubeInputAssetDiagnostic] = []
    for path in sorted(cube_root.rglob("*.cube")):
        diagnostics.extend(validate_cube(path))
    return tuple(diagnostics)


def validate_cube(path: Path) -> tuple[CubeInputAssetDiagnostic, ...]:
    """Validate one cube's asset fields and exported socket contracts."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return (CubeInputAssetDiagnostic(path, f"cannot read cube: {error}"),)
    if not isinstance(document, Mapping):
        return (CubeInputAssetDiagnostic(path, "cube root must be an object"),)
    implementation = document.get("implementation")
    if not isinstance(implementation, Mapping):
        return ()
    definitions = _definitions(implementation)
    topology = WorkflowGraphTopology(implementation, definitions)
    diagnostics: list[CubeInputAssetDiagnostic] = []
    raw_outputs = implementation.get("outputs", {})
    if isinstance(raw_outputs, Mapping) and len(topology.outputs) != len(raw_outputs):
        diagnostics.append(
            CubeInputAssetDiagnostic(
                path,
                "graph outputs must use canonical endpoints that reference existing nodes",
            )
        )

    policy = InputAssetFieldPolicy()
    asset_nodes: dict[str, int] = {}
    for node_name, node in graph_nodes(implementation).items():
        class_type = node_class_type(node)
        fields = policy.fields_for_node(class_type, definitions.get(class_type, {}))
        if not fields:
            continue
        asset_nodes[node_name] = len(fields)
        for field in fields:
            if not _ASSET_OUTPUT_TYPES.intersection(field.output_types):
                diagnostics.append(
                    CubeInputAssetDiagnostic(
                        path,
                        f"{node_name}.{field.field_key} has no IMAGE or MASK output role",
                    )
                )

    endpoint_index = InputAssetEndpointService().build_index(
        str(document.get("cube_id", path.name)),
        implementation,
        node_definitions=definitions,
    )
    discovered = {
        (endpoint.node_name, endpoint.output_index)
        for endpoint in endpoint_index.endpoints
    }
    for output in topology.outputs:
        field_count = asset_nodes.get(output.provider_name)
        if field_count != 1 or output.output_type not in _ASSET_OUTPUT_TYPES:
            continue
        if (output.provider_name, output.output_index) not in discovered:
            diagnostics.append(
                CubeInputAssetDiagnostic(
                    path,
                    "exported asset socket is not discoverable through the canonical "
                    f"endpoint contract: {output.boundary_key}",
                )
            )
    return tuple(diagnostics)


def _definitions(
    implementation: Mapping[str, object],
) -> Mapping[str, Mapping[str, object]]:
    """Return embedded live definitions with invalid records omitted."""

    raw_definitions = implementation.get("definitions", {})
    if not isinstance(raw_definitions, Mapping):
        return {}
    return {
        str(class_type): definition
        for class_type, definition in raw_definitions.items()
        if isinstance(definition, Mapping)
    }


__all__ = ["CubeInputAssetDiagnostic", "validate_cube", "validate_cube_root"]
