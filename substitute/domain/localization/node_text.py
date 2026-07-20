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

"""Define immutable Comfy catalog and node-presentation domain values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from collections.abc import Mapping

from sugarsubstitute_shared.localization import ApplicationMessage


class NodeTextSource(StrEnum):
    """Identify the authoritative layer that supplied visible node text."""

    AUTHORED = "authored"
    APPLICATION = "application"
    ACTIVE_COMFY = "active_comfy"
    ENGLISH_COMFY = "english_comfy"
    RAW_DEFINITION = "raw_definition"
    TECHNICAL_ID = "technical_id"


@dataclass(frozen=True, slots=True)
class NodeFieldCatalogText:
    """Store optional input or output presentation text from one catalog."""

    name: str | None = None
    tooltip: str | None = None


@dataclass(frozen=True, slots=True)
class NodeCatalogText:
    """Store optional node and field presentation text from one catalog."""

    display_name: str | None
    description: str | None
    inputs: Mapping[str, NodeFieldCatalogText]
    outputs: Mapping[str, NodeFieldCatalogText]

    def __post_init__(self) -> None:
        """Freeze nested field mappings supplied by strict infrastructure loaders."""

        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))
        object.__setattr__(self, "outputs", MappingProxyType(dict(self.outputs)))


@dataclass(frozen=True, slots=True)
class NodeTextCatalog:
    """Expose one validated immutable locale layer keyed by Comfy class type."""

    language_identifier: str
    source: NodeTextSource
    node_definitions: Mapping[str, NodeCatalogText]

    @classmethod
    def create(
        cls,
        *,
        language_identifier: str,
        source: NodeTextSource,
        node_definitions: Mapping[str, NodeCatalogText],
    ) -> NodeTextCatalog:
        """Freeze a validated catalog mapping under its language and source owner."""

        return cls(
            language_identifier=language_identifier,
            source=source,
            node_definitions=MappingProxyType(dict(node_definitions)),
        )


@dataclass(frozen=True, slots=True)
class ResolvedCatalogText:
    """Pair resolved visible text with its diagnostic catalog provenance."""

    text: str
    source: NodeTextSource


@dataclass(frozen=True, slots=True)
class ResolvedNodeCatalogText:
    """Return independently layered node display-name and description values."""

    display_name: ResolvedCatalogText | None = None
    description: ResolvedCatalogText | None = None


@dataclass(frozen=True, slots=True)
class ResolvedFieldCatalogText:
    """Return independently layered field name and tooltip values."""

    name: ResolvedCatalogText | None = None
    tooltip: ResolvedCatalogText | None = None


@dataclass(frozen=True, slots=True)
class NodeTextCatalogSnapshot:
    """Publish active-first and English-fallback catalog layers atomically."""

    effective_language_identifier: str
    revision: int
    active_layers: tuple[NodeTextCatalog, ...]
    english_layers: tuple[NodeTextCatalog, ...]

    @property
    def layers(self) -> tuple[NodeTextCatalog, ...]:
        """Return precedence-ordered layers without duplicating English in English mode."""

        if self.effective_language_identifier == "en":
            return self.active_layers
        return (*self.active_layers, *self.english_layers)


@dataclass(frozen=True, slots=True)
class NodeFieldPresentationRequest:
    """Describe stable and raw field text needed for one presentation projection."""

    field_key: str
    authored_label: str | None = None
    application_label: ApplicationMessage | None = None
    raw_name: str | None = None
    raw_tooltip: str | None = None


@dataclass(frozen=True, slots=True)
class NodePresentationRequest:
    """Describe locale-neutral node identity and raw fallback presentation data."""

    class_type: str
    node_name: str
    authored_title: str | None = None
    raw_display_name: str | None = None
    raw_description: str | None = None
    fields: tuple[NodeFieldPresentationRequest, ...] = ()
    outputs: tuple[NodeFieldPresentationRequest, ...] = ()


@dataclass(frozen=True, slots=True)
class FieldPresentation:
    """Project one localized field label and tooltip without changing its key."""

    field_key: str
    label: str
    tooltip: str | None
    label_source: NodeTextSource
    tooltip_source: NodeTextSource | None
    search_aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NodePresentation:
    """Project all localized text for one semantic Comfy node instance."""

    class_type: str
    title: str
    description: str | None
    card_tooltip: str | None
    title_source: NodeTextSource
    description_source: NodeTextSource | None
    fields: Mapping[str, FieldPresentation]
    outputs: Mapping[str, FieldPresentation]
    search_aliases: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        class_type: str,
        title: str,
        description: str | None,
        card_tooltip: str | None,
        title_source: NodeTextSource,
        description_source: NodeTextSource | None,
        fields: Mapping[str, FieldPresentation],
        outputs: Mapping[str, FieldPresentation],
        search_aliases: tuple[str, ...],
    ) -> NodePresentation:
        """Freeze the field projection so renderers cannot mutate shared state."""

        return cls(
            class_type=class_type,
            title=title,
            description=description,
            card_tooltip=card_tooltip,
            title_source=title_source,
            description_source=description_source,
            fields=MappingProxyType(dict(fields)),
            outputs=MappingProxyType(dict(outputs)),
            search_aliases=search_aliases,
        )


__all__ = [
    "FieldPresentation",
    "NodeCatalogText",
    "NodeFieldCatalogText",
    "NodeFieldPresentationRequest",
    "NodePresentation",
    "NodePresentationRequest",
    "NodeTextCatalog",
    "NodeTextCatalogSnapshot",
    "NodeTextSource",
    "ResolvedCatalogText",
    "ResolvedFieldCatalogText",
    "ResolvedNodeCatalogText",
]
