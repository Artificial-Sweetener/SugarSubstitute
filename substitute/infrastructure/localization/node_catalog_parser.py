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

"""Parse untrusted Comfy node-definition translations into immutable catalogs."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.domain.localization import (
    NodeCatalogText,
    NodeFieldCatalogText,
    NodeTextCatalog,
    NodeTextSource,
)

_MAX_NODE_DEFINITIONS = 20_000
_MAX_FIELDS_PER_NODE = 2_000
_MAX_TEXT_CHARACTERS = 32_768


class NodeTextCatalogParser:
    """Validate Comfy node text with strict bundled or tolerant remote policy."""

    def parse(
        self,
        raw_node_definitions: object,
        *,
        language_identifier: str,
        source: NodeTextSource,
        source_label: str,
        strict: bool,
    ) -> NodeTextCatalog:
        """Return one frozen catalog after applying bounded shape validation."""

        if not isinstance(raw_node_definitions, Mapping):
            raise ValueError(
                f"Comfy node definitions must be an object: {source_label}"
            )
        if len(raw_node_definitions) > _MAX_NODE_DEFINITIONS:
            raise ValueError(
                f"Comfy node definition count exceeds the limit: {source_label}"
            )
        parsed: dict[str, NodeCatalogText] = {}
        for class_type, raw_node in raw_node_definitions.items():
            if not isinstance(class_type, str):
                if strict:
                    raise ValueError(f"Comfy node key must be text: {source_label}")
                continue
            try:
                parsed[class_type] = self._parse_node(
                    class_type,
                    raw_node,
                    source_label=source_label,
                    strict=strict,
                )
            except ValueError:
                if strict:
                    raise
        return NodeTextCatalog.create(
            language_identifier=language_identifier,
            source=source,
            node_definitions=parsed,
        )

    def _parse_node(
        self,
        class_type: str,
        raw_node: object,
        *,
        source_label: str,
        strict: bool,
    ) -> NodeCatalogText:
        """Parse one node entry without retaining unknown remote keys."""

        if not isinstance(raw_node, Mapping):
            raise ValueError(f"Invalid node entry {class_type!r}: {source_label}")
        return NodeCatalogText(
            display_name=self._optional_text(
                raw_node.get("display_name"),
                source_label=source_label,
                strict=strict,
            ),
            description=self._optional_text(
                raw_node.get("description"),
                source_label=source_label,
                strict=strict,
            ),
            inputs=self._parse_fields(
                raw_node.get("inputs"),
                source_label=source_label,
                location=f"{class_type}.inputs",
                strict=strict,
            ),
            outputs=self._parse_fields(
                raw_node.get("outputs"),
                source_label=source_label,
                location=f"{class_type}.outputs",
                strict=strict,
            ),
        )

    def _parse_fields(
        self,
        raw_collection: object,
        *,
        source_label: str,
        location: str,
        strict: bool,
    ) -> dict[str, NodeFieldCatalogText]:
        """Parse a bounded input/output mapping and discard malformed remote entries."""

        if raw_collection is None:
            return {}
        if not isinstance(raw_collection, Mapping):
            if strict:
                raise ValueError(
                    f"Invalid field collection {location!r}: {source_label}"
                )
            return {}
        if len(raw_collection) > _MAX_FIELDS_PER_NODE:
            raise ValueError(f"Field count exceeds the limit at {location!r}")
        parsed: dict[str, NodeFieldCatalogText] = {}
        for field_key, raw_field in raw_collection.items():
            if not isinstance(field_key, str) or not isinstance(raw_field, Mapping):
                if strict:
                    raise ValueError(
                        f"Invalid field entry {location!r}: {source_label}"
                    )
                continue
            parsed[field_key] = NodeFieldCatalogText(
                name=self._optional_text(
                    raw_field.get("name"),
                    source_label=source_label,
                    strict=strict,
                ),
                tooltip=self._optional_text(
                    raw_field.get("tooltip"),
                    source_label=source_label,
                    strict=strict,
                ),
            )
        return parsed

    @staticmethod
    def _optional_text(
        value: object,
        *,
        source_label: str,
        strict: bool,
    ) -> str | None:
        """Return a bounded nonempty string under the selected trust policy."""

        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            if strict:
                raise ValueError(f"Invalid Comfy text leaf: {source_label}")
            return None
        if len(value) > _MAX_TEXT_CHARACTERS:
            if strict:
                raise ValueError(f"Comfy text leaf exceeds the limit: {source_label}")
            return None
        return value


__all__ = ["NodeTextCatalogParser"]
