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

"""Resolve authoritative localized presentation for semantic Comfy nodes."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Iterable

from sugarsubstitute_shared.localization import ApplicationMessage

from substitute.application.display_labels import beautify_label
from substitute.domain.localization import (
    FieldPresentation,
    NodeCatalogText,
    NodeFieldCatalogText,
    NodeFieldPresentationRequest,
    NodePresentation,
    NodePresentationRequest,
    NodeTextCatalog,
    NodeTextCatalogSnapshot,
    NodeTextSource,
    ResolvedCatalogText,
    ResolvedFieldCatalogText,
    ResolvedNodeCatalogText,
)

NodeTextCatalogSnapshotProvider = Callable[[], NodeTextCatalogSnapshot]
ApplicationTextRenderer = Callable[[ApplicationMessage], str]


class NodeTextCatalogResolver:
    """Resolve each node-text property independently through snapshot layers."""

    def __init__(self, snapshot: NodeTextCatalogSnapshot) -> None:
        """Retain one immutable snapshot for a bounded presentation transaction."""

        self._snapshot = snapshot

    def node_text(self, class_type: str) -> ResolvedNodeCatalogText:
        """Resolve node display name and description through all precedence layers."""

        entries = tuple(self._node_entries(class_type))
        return ResolvedNodeCatalogText(
            display_name=_first_resolved_text(
                (entry.display_name, catalog.source) for catalog, entry in entries
            ),
            description=_first_resolved_text(
                (entry.description, catalog.source) for catalog, entry in entries
            ),
        )

    def input_text(
        self,
        class_type: str,
        field_key: str,
    ) -> ResolvedFieldCatalogText:
        """Resolve one input label and tooltip without changing its stable key."""

        return self._field_text(class_type, field_key, output=False)

    def output_text(
        self,
        class_type: str,
        field_key: str,
    ) -> ResolvedFieldCatalogText:
        """Resolve one output label and tooltip without changing its stable slot."""

        return self._field_text(class_type, field_key, output=True)

    def node_search_aliases(self, class_type: str) -> tuple[str, ...]:
        """Return all localized and fallback display names for search indexing."""

        return _unique_nonempty(
            entry.display_name for _catalog, entry in self._node_entries(class_type)
        )

    def input_search_aliases(
        self,
        class_type: str,
        field_key: str,
    ) -> tuple[str, ...]:
        """Return all localized and fallback field names for search indexing."""

        return self._field_search_aliases(class_type, field_key, output=False)

    def output_search_aliases(
        self,
        class_type: str,
        field_key: str,
    ) -> tuple[str, ...]:
        """Return localized and fallback output names for search indexing."""

        return self._field_search_aliases(class_type, field_key, output=True)

    def _field_text(
        self,
        class_type: str,
        field_key: str,
        *,
        output: bool,
    ) -> ResolvedFieldCatalogText:
        """Resolve one input or output property set through catalog precedence."""

        candidates: list[tuple[NodeTextCatalog, NodeFieldCatalogText]] = []
        for catalog, node_entry in self._node_entries(class_type):
            collection = node_entry.outputs if output else node_entry.inputs
            field_entry = collection.get(field_key)
            if field_entry is not None:
                candidates.append((catalog, field_entry))
        return ResolvedFieldCatalogText(
            name=_first_resolved_text(
                (entry.name, catalog.source) for catalog, entry in candidates
            ),
            tooltip=_first_resolved_text(
                (entry.tooltip, catalog.source) for catalog, entry in candidates
            ),
        )

    def _field_search_aliases(
        self,
        class_type: str,
        field_key: str,
        *,
        output: bool,
    ) -> tuple[str, ...]:
        """Return names from every layer for one stable input or output identity."""

        aliases: list[str | None] = []
        for _catalog, node_entry in self._node_entries(class_type):
            collection = node_entry.outputs if output else node_entry.inputs
            field_entry = collection.get(field_key)
            aliases.append(field_entry.name if field_entry is not None else None)
        return _unique_nonempty(aliases)

    def _node_entries(
        self,
        class_type: str,
    ) -> Iterable[tuple[NodeTextCatalog, NodeCatalogText]]:
        """Yield exact then upstream-normalized class entries by layer precedence."""

        candidates = _class_type_candidates(class_type)
        for catalog in self._snapshot.layers:
            for candidate in candidates:
                entry = catalog.node_definitions.get(candidate)
                if entry is not None:
                    yield catalog, entry
                    break


class NodePresentationService:
    """Join authored, catalog, raw, and technical text at presentation time."""

    def __init__(
        self,
        snapshot_provider: NodeTextCatalogSnapshotProvider,
        *,
        application_text_renderer: ApplicationTextRenderer,
    ) -> None:
        """Store active Comfy and application-text projection collaborators."""

        self._snapshot_provider = snapshot_provider
        self._application_text_renderer = application_text_renderer

    def present(self, request: NodePresentationRequest) -> NodePresentation:
        """Return one immutable localized projection without mutating semantic data."""

        resolver = NodeTextCatalogResolver(self._snapshot_provider())
        catalog_node = resolver.node_text(request.class_type)
        if request.authored_title is not None:
            title = request.authored_title
            title_source = NodeTextSource.AUTHORED
        else:
            title, title_source = _resolve_visible_text(
                _resolved_pair(catalog_node.display_name),
                (_clean_text(request.raw_display_name), NodeTextSource.RAW_DEFINITION),
                (
                    _clean_text(
                        beautify_label(request.node_name or request.class_type)
                    ),
                    NodeTextSource.TECHNICAL_ID,
                ),
            )
        description, description_source = _resolve_optional_text(
            _resolved_pair(catalog_node.description),
            (_clean_text(request.raw_description), NodeTextSource.RAW_DEFINITION),
        )
        fields = self._present_fields(
            resolver,
            request.class_type,
            request.fields,
            output=False,
        )
        outputs = self._present_fields(
            resolver,
            request.class_type,
            request.outputs,
            output=True,
        )
        return NodePresentation.create(
            class_type=request.class_type,
            title=title,
            description=description,
            card_tooltip=description,
            title_source=title_source,
            description_source=description_source,
            fields=fields,
            outputs=outputs,
            search_aliases=_search_aliases(
                title if request.authored_title is None else None,
                request.raw_display_name,
                request.node_name,
                request.class_type,
                *resolver.node_search_aliases(request.class_type),
                literal_only=(request.authored_title,),
            ),
        )

    def _present_fields(
        self,
        resolver: NodeTextCatalogResolver,
        class_type: str,
        requests: tuple[NodeFieldPresentationRequest, ...],
        *,
        output: bool,
    ) -> dict[str, FieldPresentation]:
        """Project stable input or output identities without mutating node data."""

        presentations: dict[str, FieldPresentation] = {}
        for request in requests:
            catalog_field = (
                resolver.output_text(class_type, request.field_key)
                if output
                else resolver.input_text(class_type, request.field_key)
            )
            if request.authored_label is not None:
                label = request.authored_label
                label_source = NodeTextSource.AUTHORED
            elif request.application_label is not None:
                label = self._application_text_renderer(request.application_label)
                label_source = NodeTextSource.APPLICATION
            else:
                label, label_source = _resolve_visible_text(
                    _resolved_pair(catalog_field.name),
                    (_clean_text(request.raw_name), NodeTextSource.RAW_DEFINITION),
                    (
                        _clean_text(beautify_label(request.field_key)),
                        NodeTextSource.TECHNICAL_ID,
                    ),
                )
            tooltip, tooltip_source = _resolve_optional_text(
                _resolved_pair(catalog_field.tooltip),
                (_clean_text(request.raw_tooltip), NodeTextSource.RAW_DEFINITION),
            )
            aliases = (
                resolver.output_search_aliases(class_type, request.field_key)
                if output
                else resolver.input_search_aliases(class_type, request.field_key)
            )
            presentations[request.field_key] = FieldPresentation(
                field_key=request.field_key,
                label=label,
                tooltip=tooltip,
                label_source=label_source,
                tooltip_source=tooltip_source,
                search_aliases=_search_aliases(
                    (
                        label
                        if request.authored_label is None
                        and request.application_label is None
                        else None
                    ),
                    (
                        request.application_label.source_text
                        if request.application_label is not None
                        else None
                    ),
                    request.raw_name,
                    request.field_key,
                    *aliases,
                    literal_only=(request.authored_label,),
                ),
            )
        return presentations


def _class_type_candidates(class_type: str) -> tuple[str, ...]:
    """Return exact and Comfy dot-normalized lookup keys in deterministic order."""

    normalized = class_type.replace(".", "_")
    return (class_type,) if normalized == class_type else (class_type, normalized)


def _first_resolved_text(
    candidates: Iterable[tuple[str | None, NodeTextSource]],
) -> ResolvedCatalogText | None:
    """Return the first nonempty catalog property and its source layer."""

    for text, source in candidates:
        cleaned = _clean_text(text)
        if cleaned is not None:
            return ResolvedCatalogText(cleaned, source)
    return None


def _resolved_pair(
    value: ResolvedCatalogText | None,
) -> tuple[str | None, NodeTextSource]:
    """Adapt an optional catalog value for shared precedence helpers."""

    if value is None:
        return None, NodeTextSource.TECHNICAL_ID
    return value.text, value.source


def _resolve_visible_text(
    *candidates: tuple[str | None, NodeTextSource],
) -> tuple[str, NodeTextSource]:
    """Return the first required visible value from a complete fallback chain."""

    for text, source in candidates:
        cleaned = _clean_text(text)
        if cleaned is not None:
            return cleaned, source
    raise ValueError("A node presentation fallback chain produced no visible text.")


def _resolve_optional_text(
    *candidates: tuple[str | None, NodeTextSource],
) -> tuple[str | None, NodeTextSource | None]:
    """Return the first optional tooltip/description and its source."""

    for text, source in candidates:
        cleaned = _clean_text(text)
        if cleaned is not None:
            return cleaned, source
    return None, None


def _clean_text(value: str | None) -> str | None:
    """Normalize surrounding whitespace without changing authored Unicode content."""

    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _unique_nonempty(values: Iterable[str | None]) -> tuple[str, ...]:
    """Return distinct nonempty values while preserving precedence order."""

    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        if cleaned is None or cleaned in seen:
            continue
        seen.add(cleaned)
        unique.append(cleaned)
    return tuple(unique)


def _unique_exact(values: Iterable[str]) -> tuple[str, ...]:
    """Deduplicate literal authored values without normalization or trimming."""

    return tuple(dict.fromkeys(values))


def _search_aliases(
    *values: str | None,
    literal_only: tuple[str | None, ...] = (),
) -> tuple[str, ...]:
    """Normalize derived labels while retaining authored aliases byte-for-byte."""

    literals = _unique_nonempty(values)
    normalized = _unique_nonempty(
        unicodedata.normalize("NFKC", value).casefold() for value in literals
    )
    exact_authored = tuple(value for value in literal_only if value is not None)
    return _unique_exact((*exact_authored, *_unique_nonempty((*literals, *normalized))))


__all__ = [
    "ApplicationTextRenderer",
    "NodePresentationService",
    "NodeTextCatalogResolver",
    "NodeTextCatalogSnapshotProvider",
]
