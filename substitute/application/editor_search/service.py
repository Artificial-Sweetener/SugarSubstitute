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

"""Compute editor-search matches from authoritative behavior snapshots."""

from __future__ import annotations

from typing import Iterable

from substitute.application.display_labels import beautify_label
from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    ResolvedFieldSpec,
)

from .models import (
    EditorSearchMode,
    EditorSearchQuery,
    EditorSearchResult,
    TextSearchMatch,
)


class EditorSearchService:
    """Own query parsing and authoritative search matching for editor state."""

    def build_query(
        self,
        *,
        mode: EditorSearchMode,
        raw_text: str,
    ) -> EditorSearchQuery:
        """Parse one raw search string into mode-specific normalized fields."""

        stripped_text = raw_text.strip()
        normalized_text = stripped_text.lower()
        if mode is EditorSearchMode.NODE:
            node_filter_text, text_filter_text = self._split_node_query(stripped_text)
            return EditorSearchQuery(
                mode=mode,
                raw_text=raw_text,
                normalized_text=normalized_text,
                node_filter_text=node_filter_text.lower(),
                text_filter_text=text_filter_text.lower(),
                tokens=tuple(
                    token for token in node_filter_text.lower().split() if token
                ),
            )
        if mode is EditorSearchMode.FIELD:
            return EditorSearchQuery(
                mode=mode,
                raw_text=raw_text,
                normalized_text=normalized_text,
                node_filter_text="",
                text_filter_text="",
                tokens=tuple(token for token in normalized_text.split() if token),
            )
        return EditorSearchQuery(
            mode=mode,
            raw_text=raw_text,
            normalized_text=normalized_text,
            node_filter_text="",
            text_filter_text="",
            tokens=tuple(token for token in normalized_text.split() if token),
        )

    def build_result(
        self,
        snapshot: EditorBehaviorSnapshot,
        query: EditorSearchQuery,
    ) -> EditorSearchResult:
        """Compute matches for one query against an authoritative behavior snapshot."""

        matching_nodes = self._matching_nodes(snapshot, query)
        matching_fields = self._matching_fields(snapshot, query)
        text_scope = self._text_scope(query=query, matching_nodes=matching_nodes)
        text_matches = self._text_matches(
            snapshot,
            query,
            scoped_nodes=text_scope,
        )
        navigation_matches = (
            text_matches
            if (
                query.mode is EditorSearchMode.TEXT
                or (
                    query.mode is EditorSearchMode.NODE and bool(query.text_filter_text)
                )
            )
            else ()
        )
        return EditorSearchResult(
            query=query,
            matching_nodes=matching_nodes,
            matching_fields=matching_fields,
            text_matches=text_matches,
            navigation_matches=navigation_matches,
        )

    def _matching_nodes(
        self,
        snapshot: EditorBehaviorSnapshot,
        query: EditorSearchQuery,
    ) -> set[tuple[str, str]]:
        """Return node matches for node and field filtering modes."""

        if query.mode is EditorSearchMode.FIELD:
            if not query.tokens:
                return self._all_node_keys(snapshot)
            matching_fields = self._matching_fields(snapshot, query)
            return {
                (cube_alias, node_name)
                for cube_alias, node_name, _field_key in matching_fields
            }

        if query.mode is not EditorSearchMode.NODE:
            return set()

        if not query.node_filter_text:
            return self._all_node_keys(snapshot)

        matching_nodes: set[tuple[str, str]] = set()
        for cube_alias, per_node in snapshot.resolved_nodes_by_alias.items():
            field_specs_by_node = snapshot.field_specs_by_alias.get(cube_alias, {})
            for node_name, resolved_behavior in per_node.items():
                if self._node_matches_query(
                    query.node_filter_text,
                    node_name=node_name,
                    class_type=resolved_behavior.class_type,
                    field_specs=field_specs_by_node.get(node_name, {}).values(),
                ):
                    matching_nodes.add((cube_alias, node_name))
        return matching_nodes

    def _matching_fields(
        self,
        snapshot: EditorBehaviorSnapshot,
        query: EditorSearchQuery,
    ) -> set[tuple[str, str, str]]:
        """Return canonical field keys that match one field-mode query."""

        if query.mode is not EditorSearchMode.FIELD:
            return set()
        if not query.tokens:
            return {
                (cube_alias, node_name, field_key)
                for cube_alias, per_node in snapshot.field_specs_by_alias.items()
                for node_name, field_specs in per_node.items()
                for field_key in field_specs
            }

        matching_fields: set[tuple[str, str, str]] = set()
        for cube_alias, per_node in snapshot.field_specs_by_alias.items():
            for node_name, field_specs in per_node.items():
                for field_key, field_spec in field_specs.items():
                    searchable_field_text = self._normalized_field_search_text(
                        field_spec
                    )
                    if all(token in searchable_field_text for token in query.tokens):
                        matching_fields.add((cube_alias, node_name, field_key))
        return matching_fields

    def _text_matches(
        self,
        snapshot: EditorBehaviorSnapshot,
        query: EditorSearchQuery,
        *,
        scoped_nodes: set[tuple[str, str]] | None,
    ) -> tuple[TextSearchMatch, ...]:
        """Return ordered text matches within the requested search scope."""

        needle = (
            query.normalized_text
            if query.mode is EditorSearchMode.TEXT
            else query.text_filter_text
        )
        if not needle:
            return ()

        matches: list[TextSearchMatch] = []
        for cube_alias, per_node in snapshot.field_specs_by_alias.items():
            for node_name, field_specs in per_node.items():
                node_key = (cube_alias, node_name)
                if scoped_nodes is not None and node_key not in scoped_nodes:
                    continue
                for field_key, field_spec in field_specs.items():
                    searchable_text = self._searchable_text_value(field_spec)
                    if searchable_text is None:
                        continue
                    start = searchable_text.lower().find(needle)
                    while start != -1:
                        matches.append(
                            TextSearchMatch(
                                cube_alias=cube_alias,
                                node_name=node_name,
                                field_key=field_key,
                                start=start,
                                length=len(needle),
                            )
                        )
                        next_start = start + max(1, len(needle))
                        start = searchable_text.lower().find(needle, next_start)
        return tuple(matches)

    @staticmethod
    def _split_node_query(raw_text: str) -> tuple[str, str]:
        """Split one mixed node query into node and quoted text portions."""

        first_quote = raw_text.find('"')
        if first_quote == -1:
            return raw_text.strip(), ""
        node_filter_text = raw_text[:first_quote].strip()
        after_quote = raw_text[first_quote + 1 :]
        second_quote = after_quote.find('"')
        if second_quote == -1:
            return node_filter_text, after_quote.strip()
        return node_filter_text, after_quote[:second_quote].strip()

    @staticmethod
    def _text_scope(
        *,
        query: EditorSearchQuery,
        matching_nodes: set[tuple[str, str]],
    ) -> set[tuple[str, str]] | None:
        """Return the node scope used for text matches in the current query."""

        if query.mode is not EditorSearchMode.NODE or not query.text_filter_text:
            return None
        if not query.node_filter_text:
            return None
        return matching_nodes

    @staticmethod
    def _all_node_keys(
        snapshot: EditorBehaviorSnapshot,
    ) -> set[tuple[str, str]]:
        """Return every node key represented in the snapshot."""

        return {
            (cube_alias, node_name)
            for cube_alias, per_node in snapshot.field_specs_by_alias.items()
            for node_name in per_node
        }

    def _node_matches_query(
        self,
        needle: str,
        *,
        node_name: str,
        class_type: str,
        field_specs: Iterable[ResolvedFieldSpec],
    ) -> bool:
        """Return whether one node should remain visible for the supplied query."""

        corpus = [
            node_name.lower(),
            class_type.lower(),
        ]
        for field_spec in field_specs:
            corpus.append(field_spec.field_key.lower())
            corpus.append(self._field_label(field_spec).lower())
        return any(needle in text for text in corpus)

    def _normalized_field_search_text(self, field_spec: ResolvedFieldSpec) -> str:
        """Return the normalized searchable text used by field-mode matching."""

        return " ".join(
            (
                field_spec.field_key.lower(),
                self._field_label(field_spec).lower(),
            )
        )

    @staticmethod
    def _field_label(field_spec: ResolvedFieldSpec) -> str:
        """Return the effective user-facing field label for search matching."""

        label_override = field_spec.field_behavior.label_override
        if isinstance(label_override, str) and label_override.strip():
            return label_override.strip()
        metadata_label = field_spec.meta_info.get("label")
        if isinstance(metadata_label, str) and metadata_label.strip():
            return metadata_label.strip()
        return beautify_label(field_spec.field_key)

    @staticmethod
    def _searchable_text_value(field_spec: ResolvedFieldSpec) -> str | None:
        """Return the authoritative source text for one text-searchable field."""

        value = field_spec.value
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        return None
