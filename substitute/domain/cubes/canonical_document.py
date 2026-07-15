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

"""Validate canonical SugarCube documents and materialize runtime graphs."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from substitute.domain.common import JsonObject


class CanonicalCubeError(ValueError):
    """Represent a canonical cube document contract violation."""


@dataclass(frozen=True)
class CanonicalCubeDocument:
    """Store a validated current-format SugarCube document."""

    cube_id: str
    version: str
    description: str
    metadata: dict[str, Any]
    implementation: dict[str, Any]
    surface: dict[str, Any]
    flavors: dict[str, list[dict[str, Any]]]

    @property
    def default_flavor_id(self) -> str:
        """Return the authored flavor id used for default runtime materialization."""

        return str(self.surface["default_flavor_id"])

    @property
    def display_name(self) -> str:
        """Return display metadata without changing canonical identity."""

        default_alias = self.metadata.get("default_alias")
        if isinstance(default_alias, str) and default_alias.strip():
            return default_alias.strip()
        name = self.metadata.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
        return self.cube_id

    def to_metadata_payload(self, selected_flavor_id: str | None = None) -> JsonObject:
        """Return canonical metadata to attach beside the materialized runtime graph."""

        return {
            "cube_id": self.cube_id,
            "version": self.version,
            "description": self.description,
            "metadata": copy.deepcopy(self.metadata),
            "surface": copy.deepcopy(self.surface),
            "flavors": copy.deepcopy(self.flavors),
            "selected_flavor_id": selected_flavor_id or self.default_flavor_id,
        }


def validate_canonical_cube_document(
    payload: Mapping[str, Any],
) -> CanonicalCubeDocument:
    """Validate and normalize a current-format SugarCube document."""

    if not isinstance(payload, Mapping):
        raise CanonicalCubeError("Cube root must be a JSON object.")

    cube_id = _require_string(payload, "cube_id", "Cube document")
    version = _require_string(payload, "version", "Cube document")
    implementation = _require_mapping(payload, "implementation", "Cube document")
    surface = _validate_surface(_require_mapping(payload, "surface", "Cube document"))
    flavors = _validate_flavors(_require_mapping(payload, "flavors", "Cube document"))

    nodes = _require_mapping(implementation, "nodes", "Cube implementation")
    if not nodes:
        raise CanonicalCubeError("Cube implementation must include non-empty nodes.")
    normalized_implementation = {
        "nodes": _validate_implementation_nodes(nodes),
        "inputs": copy.deepcopy(
            _require_mapping(implementation, "inputs", "Cube implementation")
        ),
        "outputs": copy.deepcopy(
            _require_mapping(implementation, "outputs", "Cube implementation")
        ),
        "layout": copy.deepcopy(
            _require_mapping(implementation, "layout", "Cube implementation")
        ),
        "definitions": copy.deepcopy(
            _require_mapping(implementation, "definitions", "Cube implementation")
        ),
        "subgraphs": copy.deepcopy(
            _require_list(implementation, "subgraphs", "Cube implementation")
        ),
    }
    _validate_surface_flavor_contract(surface, flavors)
    return CanonicalCubeDocument(
        cube_id=cube_id,
        version=version,
        description=_optional_string(payload.get("description")),
        metadata=copy.deepcopy(_optional_mapping(payload.get("metadata"))),
        implementation=normalized_implementation,
        surface=surface,
        flavors=flavors,
    )


def materialize_cube_runtime_graph(
    document: CanonicalCubeDocument,
    *,
    authored_flavor_id: str | None = None,
) -> JsonObject:
    """Return the flat runtime graph expected by Substitute editor workflows."""

    flavor_id = authored_flavor_id or document.default_flavor_id
    runtime_nodes = copy.deepcopy(document.implementation["nodes"])
    flavor = _find_authored_flavor(document.flavors["authored"], flavor_id)
    if flavor is None:
        raise CanonicalCubeError(f"Authored flavor '{flavor_id}' is not available.")
    _apply_control_values(runtime_nodes, document.surface["controls"], flavor["values"])
    return {
        "cube_id": document.cube_id,
        "version": document.version,
        "nodes": runtime_nodes,
        "inputs": copy.deepcopy(document.implementation["inputs"]),
        "outputs": copy.deepcopy(document.implementation["outputs"]),
        "layout": copy.deepcopy(document.implementation["layout"]),
        "definitions": copy.deepcopy(document.implementation["definitions"]),
        "subgraphs": copy.deepcopy(document.implementation["subgraphs"]),
        "surface": copy.deepcopy(document.surface),
        "flavors": copy.deepcopy(document.flavors),
        "selected_flavor_id": flavor_id,
    }


def _apply_control_values(
    runtime_nodes: dict[str, Any],
    controls: list[dict[str, str]],
    values: Mapping[str, Any],
) -> None:
    """Overlay authored flavor values onto materialized implementation nodes."""

    controls_by_id = {control["control_id"]: control for control in controls}
    for control_id, value in values.items():
        control = controls_by_id[control_id]
        node = runtime_nodes.get(control["symbol"])
        if not isinstance(node, dict):
            continue
        inputs = node.setdefault("inputs", {})
        if not isinstance(inputs, dict):
            raise CanonicalCubeError(
                f"Cube node '{control['symbol']}' inputs must be an object."
            )
        inputs[control["input_name"]] = copy.deepcopy(value)


def _find_authored_flavor(
    authored_flavors: list[dict[str, Any]],
    flavor_id: str,
) -> dict[str, Any] | None:
    """Return an authored flavor by id."""

    for flavor in authored_flavors:
        if flavor["id"] == flavor_id:
            return flavor
    return None


def _validate_surface(surface: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize surface controls."""

    default_flavor_id = _require_string(surface, "default_flavor_id", "Cube surface")
    controls_payload = _require_list(surface, "controls", "Cube surface")
    controls: list[dict[str, str]] = []
    seen_control_ids: set[str] = set()
    seen_labels_by_symbol: dict[str, set[str]] = {}
    for index, control_payload in enumerate(controls_payload):
        if not isinstance(control_payload, dict):
            raise CanonicalCubeError(
                f"Cube surface control #{index + 1} must be an object."
            )
        control = {
            "control_id": _require_string(
                control_payload, "control_id", "Cube surface control"
            ),
            "symbol": _require_string(
                control_payload, "symbol", "Cube surface control"
            ),
            "input_name": _require_string(
                control_payload, "input_name", "Cube surface control"
            ),
            "label": _require_string(control_payload, "label", "Cube surface control"),
            "class_type": _require_string(
                control_payload, "class_type", "Cube surface control"
            ),
            "value_type": _require_string(
                control_payload, "value_type", "Cube surface control"
            ),
        }
        if control["control_id"] in seen_control_ids:
            raise CanonicalCubeError(
                f"Cube surface has duplicate control id '{control['control_id']}'."
            )
        seen_control_ids.add(control["control_id"])
        symbol_labels = seen_labels_by_symbol.setdefault(control["symbol"], set())
        if control["label"] in symbol_labels:
            raise CanonicalCubeError(
                "Cube surface has duplicate label "
                f"'{control['label']}' for symbol '{control['symbol']}'."
            )
        symbol_labels.add(control["label"])
        controls.append(control)
    return {"default_flavor_id": default_flavor_id, "controls": controls}


def _validate_implementation_nodes(nodes: dict[str, Any]) -> dict[str, Any]:
    """Validate implementation nodes and normalize script-facing labels."""

    normalized_nodes: dict[str, Any] = {}
    seen_labels: dict[str, str] = {}
    for node_key, node_payload in nodes.items():
        if not isinstance(node_key, str) or not node_key.strip():
            raise CanonicalCubeError("Cube implementation node keys must be non-empty.")
        if not isinstance(node_payload, Mapping):
            raise CanonicalCubeError(
                f"Cube implementation node '{node_key}' must be an object."
            )
        node = copy.deepcopy(dict(node_payload))
        label = _optional_string(node.get("label")) or node_key
        previous = seen_labels.get(label)
        if previous is not None:
            raise CanonicalCubeError(
                "Cube implementation has duplicate node label "
                f"'{label}' for node keys '{previous}' and '{node_key}'."
            )
        seen_labels[label] = node_key
        node["label"] = label
        normalized_nodes[node_key] = node
    return normalized_nodes


def _validate_flavors(flavors: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Validate authored flavor records."""

    authored_payload = _require_list(flavors, "authored", "Cube flavors")
    if not authored_payload:
        raise CanonicalCubeError(
            "Cube flavors must include at least one authored flavor."
        )
    authored: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, flavor_payload in enumerate(authored_payload):
        if not isinstance(flavor_payload, dict):
            raise CanonicalCubeError(f"Authored flavor #{index + 1} must be an object.")
        flavor_id = _require_string(flavor_payload, "id", "Authored flavor")
        if flavor_id in seen_ids:
            raise CanonicalCubeError(
                f"Cube flavors have duplicate authored id '{flavor_id}'."
            )
        seen_ids.add(flavor_id)
        authored.append(
            {
                "id": flavor_id,
                "name": _require_string(flavor_payload, "name", "Authored flavor"),
                "values": copy.deepcopy(
                    _require_mapping(flavor_payload, "values", "Authored flavor")
                ),
            }
        )
    if authored[0]["id"] != "default":
        raise CanonicalCubeError("Default authored flavor must be stored first.")
    return {"authored": authored}


def _validate_surface_flavor_contract(
    surface: dict[str, Any],
    flavors: dict[str, list[dict[str, Any]]],
) -> None:
    """Validate flavor references against the declared surface."""

    authored_ids = {flavor["id"] for flavor in flavors["authored"]}
    if surface["default_flavor_id"] not in authored_ids:
        raise CanonicalCubeError(
            "surface.default_flavor_id must reference an authored flavor."
        )
    control_ids = {control["control_id"] for control in surface["controls"]}
    for flavor in flavors["authored"]:
        unknown = sorted(set(flavor["values"]) - control_ids)
        if unknown:
            raise CanonicalCubeError(
                f"Authored flavor '{flavor['id']}' references unknown surface control(s): {', '.join(unknown)}."
            )


def _require_string(payload: Mapping[str, Any], key: str, owner: str) -> str:
    """Read a required non-empty string field."""

    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CanonicalCubeError(f"{owner} must include a non-empty '{key}'.")
    return value.strip()


def _require_mapping(
    payload: Mapping[str, Any],
    key: str,
    owner: str,
) -> dict[str, Any]:
    """Read a required object field."""

    value = payload.get(key)
    if not isinstance(value, dict):
        raise CanonicalCubeError(f"{owner} must include a '{key}' object.")
    return value


def _require_list(payload: Mapping[str, Any], key: str, owner: str) -> list[Any]:
    """Read a required array field."""

    value = payload.get(key)
    if not isinstance(value, list):
        raise CanonicalCubeError(f"{owner} must include a '{key}' array.")
    return value


def _optional_mapping(value: Any) -> dict[str, Any]:
    """Return an optional object field as a dictionary."""

    if isinstance(value, dict):
        return value
    return {}


def _optional_string(value: Any) -> str:
    """Return an optional string field as stripped text."""

    if isinstance(value, str):
        return value.strip()
    return ""
