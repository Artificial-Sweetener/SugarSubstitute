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

"""Resolve required node metadata from live Comfy definitions only."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass

from substitute.application.ports import NodeDefinitionGateway


@dataclass(frozen=True, slots=True)
class MissingLiveNodeDefinition:
    """Describe one missing required live Comfy node definition."""

    class_type: str
    cube_aliases: tuple[str, ...] = ()
    node_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LiveNodeFieldDefinition:
    """Carry one field definition resolved from live Comfy metadata."""

    class_type: str
    field_key: str
    field_type: str | None
    meta_info: dict[str, object]
    field_info: list[object] | None


class LiveNodeDefinitionError(RuntimeError):
    """Raised when required live Comfy node metadata is unavailable."""

    def __init__(
        self,
        *,
        operation: str,
        missing_definitions: Sequence[MissingLiveNodeDefinition],
        missing_fields: Sequence[LiveNodeFieldDefinition] = (),
    ) -> None:
        """Initialize the error with missing classes and fields."""

        self.operation = operation
        self.missing_definitions = tuple(missing_definitions)
        self.missing_fields = tuple(missing_fields)
        super().__init__(self._message())

    def _message(self) -> str:
        """Return a concise diagnostic message for logs and modal reports."""

        missing_classes = ", ".join(
            item.class_type for item in self.missing_definitions
        )
        missing_fields = ", ".join(
            f"{item.class_type}.{item.field_key}" for item in self.missing_fields
        )
        parts = [f"Live Comfy metadata unavailable during {self.operation}."]
        if missing_classes:
            parts.append(f"Missing definitions: {missing_classes}.")
        if missing_fields:
            parts.append(f"Missing fields: {missing_fields}.")
        return " ".join(parts)


class LiveNodeDefinitionAuthority:
    """Provide live-only Comfy node definitions and field metadata."""

    def __init__(self, node_definition_gateway: NodeDefinitionGateway) -> None:
        """Store the live Comfy node-definition gateway."""

        self._node_definition_gateway = node_definition_gateway

    def get_required_definition(
        self,
        class_type: str,
        *,
        operation: str,
        cube_aliases: Sequence[str] = (),
        node_names: Sequence[str] = (),
    ) -> Mapping[str, object]:
        """Return one required live Comfy node definition or raise."""

        payload = self._node_definition_gateway.get_required_node_definition(class_type)
        definition = payload.get(class_type) if isinstance(payload, Mapping) else None
        if isinstance(definition, Mapping):
            return deepcopy(dict(definition))
        raise LiveNodeDefinitionError(
            operation=operation,
            missing_definitions=(
                MissingLiveNodeDefinition(
                    class_type=class_type,
                    cube_aliases=tuple(cube_aliases),
                    node_names=tuple(node_names),
                ),
            ),
        )

    def get_required_field(
        self,
        class_type: str,
        field_key: str,
        *,
        operation: str,
        cube_aliases: Sequence[str] = (),
        node_names: Sequence[str] = (),
    ) -> LiveNodeFieldDefinition:
        """Return one required live Comfy field definition or raise."""

        definition = self.get_required_definition(
            class_type,
            operation=operation,
            cube_aliases=cube_aliases,
            node_names=node_names,
        )
        field_info = _field_info_from_definition(definition, field_key)
        if field_info is None:
            raise LiveNodeDefinitionError(
                operation=operation,
                missing_definitions=(),
                missing_fields=(
                    LiveNodeFieldDefinition(
                        class_type=class_type,
                        field_key=field_key,
                        field_type=None,
                        meta_info={},
                        field_info=None,
                    ),
                ),
            )
        field_type, meta_info = _field_type_and_metadata(field_info)
        return LiveNodeFieldDefinition(
            class_type=class_type,
            field_key=field_key,
            field_type=field_type,
            meta_info=meta_info,
            field_info=field_info,
        )


def _field_info_from_definition(
    definition: Mapping[str, object],
    field_key: str,
) -> list[object] | None:
    """Return raw live field info from required or optional sections."""

    input_section = definition.get("input")
    if not isinstance(input_section, Mapping):
        return None
    for section_name in ("required", "optional"):
        section = input_section.get(section_name)
        if not isinstance(section, Mapping):
            continue
        field_info = section.get(field_key)
        if isinstance(field_info, Sequence) and not isinstance(
            field_info,
            (str, bytes),
        ):
            return list(field_info)
    return None


def _field_type_and_metadata(
    field_info: Sequence[object],
) -> tuple[str | None, dict[str, object]]:
    """Return a renderable field type and metadata from live field info."""

    if not field_info:
        return None, {}
    field_type: str | None = None
    first_item = field_info[0]
    if isinstance(first_item, str):
        stripped = first_item.strip()
        field_type = stripped or None
    elif isinstance(first_item, Sequence) and not isinstance(first_item, (str, bytes)):
        field_type = "LIST"

    meta_info: dict[str, object] = {}
    if len(field_info) >= 2 and isinstance(field_info[1], Mapping):
        meta_info = deepcopy(dict(field_info[1]))
    return field_type, meta_info


__all__ = [
    "LiveNodeDefinitionAuthority",
    "LiveNodeDefinitionError",
    "LiveNodeFieldDefinition",
    "MissingLiveNodeDefinition",
]
