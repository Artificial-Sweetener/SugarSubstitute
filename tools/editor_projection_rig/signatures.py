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

"""Build pure settled-signature models from captured editor projection fixtures."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, cast


@dataclass(frozen=True, slots=True)
class FieldSignature:
    """Describe one field/control in a settled node card."""

    field_key: str
    value_repr: str
    visible: bool


@dataclass(frozen=True, slots=True)
class NodeCardSignature:
    """Describe one settled node card independent of Qt."""

    node_name: str
    node_class: str
    visible: bool
    enabled: bool
    fields: tuple[FieldSignature, ...]


@dataclass(frozen=True, slots=True)
class CubeSectionSignature:
    """Describe one settled cube section independent of Qt."""

    alias: str
    cube_id: str
    version: str
    node_cards: tuple[NodeCardSignature, ...]


@dataclass(frozen=True, slots=True)
class EditorSettledSignature:
    """Describe the final editor projection state used for fixture comparisons."""

    workflow_id: str
    cube_sections: tuple[CubeSectionSignature, ...]
    parent_chain_violations: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-compatible representation of this signature."""

        return cast(dict[str, Any], json.loads(json.dumps(asdict(self))))


def signature_from_fixture(fixture: Mapping[str, Any]) -> EditorSettledSignature:
    """Build a deterministic settled signature from one captured workflow fixture."""

    cubes = fixture.get("cubes", [])
    cube_sections: list[CubeSectionSignature] = []
    if not isinstance(cubes, list):
        cubes = []
    for raw_cube in cubes:
        if not isinstance(raw_cube, Mapping):
            continue
        cube_buffer = _mapping(raw_cube.get("cube_buffer"))
        implementation = _mapping(cube_buffer.get("implementation"))
        nodes = _mapping(implementation.get("nodes"))
        node_cards = tuple(
            _node_card_signature(node_name, nodes[node_name])
            for node_name in sorted(nodes)
            if isinstance(nodes[node_name], Mapping)
        )
        cube_sections.append(
            CubeSectionSignature(
                alias=str(raw_cube.get("alias", "")),
                cube_id=str(raw_cube.get("cube_id", "")),
                version=str(raw_cube.get("version", "")),
                node_cards=node_cards,
            )
        )
    return EditorSettledSignature(
        workflow_id=str(fixture.get("workflow_id", "")),
        cube_sections=tuple(cube_sections),
    )


def _node_card_signature(
    node_name: str,
    node_data: Mapping[str, Any],
) -> NodeCardSignature:
    """Build a deterministic node-card signature from captured node data."""

    inputs = _mapping(node_data.get("inputs"))
    fields = tuple(
        FieldSignature(
            field_key=str(key),
            value_repr=repr(inputs[key]),
            visible=True,
        )
        for key in sorted(inputs)
    )
    return NodeCardSignature(
        node_name=str(node_name),
        node_class=str(node_data.get("class_type", "")),
        visible=True,
        enabled=True,
        fields=fields,
    )


def _mapping(value: object) -> Mapping[str, Any]:
    """Return a mapping value or an empty mapping."""

    return value if isinstance(value, Mapping) else {}
