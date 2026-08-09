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

"""Define the canonical boundary between authored and structural cube inputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeGuard


class CubeAuthoringContractError(ValueError):
    """Reject cube graphs whose authored-input ownership is ambiguous."""


@dataclass(frozen=True, slots=True, order=True)
class CubeInputField:
    """Identify one implementation-node input independently from its value."""

    node_key: str
    input_key: str


@dataclass(frozen=True, slots=True)
class CubeAuthoringContract:
    """Store fields explicitly owned by the cube's authored surface contract."""

    authored_fields: tuple[CubeInputField, ...]

    @classmethod
    def from_graph(cls, graph: Mapping[str, object]) -> CubeAuthoringContract:
        """Build an authoring contract from canonical surface and boundary topology."""

        surface = graph.get("surface")
        if not isinstance(surface, Mapping):
            raise CubeAuthoringContractError(
                "Cube graph must include a canonical surface contract."
            )
        controls = surface.get("controls")
        if not _is_sequence(controls):
            raise CubeAuthoringContractError(
                "Cube surface must include an ordered controls collection."
            )

        authored_fields: list[CubeInputField] = []
        seen_fields: set[CubeInputField] = set()
        for index, control in enumerate(controls):
            if not isinstance(control, Mapping):
                raise CubeAuthoringContractError(
                    f"Cube surface control #{index + 1} must be an object."
                )
            field = CubeInputField(
                node_key=_required_text(control, "symbol", index),
                input_key=_required_text(control, "input_name", index),
            )
            if field in seen_fields:
                raise CubeAuthoringContractError(
                    "Cube surface declares the same authored input more than once: "
                    f"{field.node_key}.{field.input_key}."
                )
            seen_fields.add(field)
            authored_fields.append(field)

        boundary_fields = _boundary_target_fields(graph.get("inputs"))
        conflicts = sorted(seen_fields & boundary_fields)
        if conflicts:
            formatted = ", ".join(
                f"{field.node_key}.{field.input_key}" for field in conflicts
            )
            raise CubeAuthoringContractError(
                "Cube inputs cannot be both surface-authored and boundary-owned: "
                f"{formatted}."
            )
        return cls(authored_fields=tuple(authored_fields))


def _boundary_target_fields(value: object) -> set[CubeInputField]:
    """Return concrete implementation inputs owned by public cube boundaries."""

    if not isinstance(value, Mapping):
        raise CubeAuthoringContractError("Cube inputs must be an object.")
    fields: set[CubeInputField] = set()
    for binding_name, binding in value.items():
        if not isinstance(binding_name, str) or not binding_name:
            raise CubeAuthoringContractError("Cube input names must be non-empty text.")
        targets: object = (
            binding.get("targets") if isinstance(binding, Mapping) else binding
        )
        if isinstance(targets, str):
            continue
        if not _is_sequence(targets):
            raise CubeAuthoringContractError(
                f"Cube input '{binding_name}' must declare target pairs."
            )
        for target in targets:
            if not _is_sequence(target) or len(target) != 2:
                raise CubeAuthoringContractError(
                    f"Cube input '{binding_name}' contains an invalid target."
                )
            node_key, input_key = target
            if not isinstance(node_key, str) or not isinstance(input_key, str):
                raise CubeAuthoringContractError(
                    f"Cube input '{binding_name}' targets must contain text keys."
                )
            fields.add(CubeInputField(node_key=node_key, input_key=input_key))
    return fields


def _required_text(control: Mapping[object, object], key: str, index: int) -> str:
    """Return one required surface-control identity component."""

    value = control.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CubeAuthoringContractError(
            f"Cube surface control #{index + 1} must include non-empty '{key}'."
        )
    return value.strip()


def _is_sequence(value: object) -> TypeGuard[Sequence[object]]:
    """Return whether a value is a non-text sequence."""

    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


__all__ = [
    "CubeAuthoringContract",
    "CubeAuthoringContractError",
    "CubeInputField",
]
