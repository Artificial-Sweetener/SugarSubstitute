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

"""Own node and field visibility state derived from editor search results."""

from __future__ import annotations

from typing import Protocol

from substitute.application.editor_search import EditorSearchResult


class SearchVisibilityHost(Protocol):
    """Describe behavior refresh and field visibility commands for search."""

    _current_node_search_text: str | None
    _current_search_hidden_keys: set[object]
    _current_search_matching_nodes: set[tuple[str, str]] | None

    def refresh_node_behavior_state(
        self,
        search_hidden_keys: set[object] | None = None,
        node_search_text: str | None = None,
        search_matching_nodes: set[tuple[str, str]] | None = None,
        *,
        reason: str = "search_changed",
    ) -> None:
        """Refresh behavior visibility for search state."""

    def set_search_field_match_keys(
        self,
        match_keys: set[tuple[str, str, str]] | None,
        *,
        active: bool,
    ) -> None:
        """Publish field-search match keys to hidden-field ownership."""


class SearchVisibilityController:
    """Translate search modes into node and field visibility commands."""

    def __init__(self, host: SearchVisibilityHost) -> None:
        """Store behavior commands and initialize unfiltered visibility."""

        self._host = host
        self._node_search_text: str | None = None
        self._hidden_keys: set[object] = set()
        self._matching_nodes: set[tuple[str, str]] | None = None

    def apply(self, result: EditorSearchResult) -> None:
        """Apply visibility filters for one newly submitted search result."""

        if result.query.mode.value == "field" and result.query.tokens:
            self._node_search_text = None
            self._hidden_keys = set()
            self._matching_nodes = set(result.matching_nodes)
            self._set_field_matches(result.matching_fields, active=True)
            self.publish()
            self._host.refresh_node_behavior_state(
                search_hidden_keys=set(),
                node_search_text=None,
                search_matching_nodes=result.matching_nodes,
                reason="search_changed",
            )
            return
        if result.query.mode.value == "node" and result.query.node_filter_text:
            self._set_field_matches(None, active=False)
            self._hidden_keys = set()
            self._node_search_text = None
            self._matching_nodes = set(result.matching_nodes)
            self.publish()
            self._host.refresh_node_behavior_state(
                search_hidden_keys=set(),
                node_search_text=None,
                search_matching_nodes=result.matching_nodes,
                reason="search_changed",
            )
            return
        self.clear()

    def clear(self) -> None:
        """Clear node and field filters while preserving other search state."""

        self._node_search_text = None
        self._hidden_keys = set()
        self._matching_nodes = None
        self._set_field_matches(None, active=False)
        self.publish()
        self._host.refresh_node_behavior_state(
            search_hidden_keys=set(),
            node_search_text=None,
            reason="search_changed",
        )

    def publish(self) -> None:
        """Mirror current visibility state for adjacent transitional owners."""

        self._host._current_node_search_text = self._node_search_text
        self._host._current_search_hidden_keys = set(self._hidden_keys)
        self._host._current_search_matching_nodes = (
            None if self._matching_nodes is None else set(self._matching_nodes)
        )

    def _set_field_matches(
        self,
        match_keys: set[tuple[str, str, str]] | None,
        *,
        active: bool,
    ) -> None:
        """Apply field-search state through the focused field-sync command."""

        set_matches = getattr(self._host, "set_search_field_match_keys", None)
        if callable(set_matches):
            set_matches(match_keys, active=active)


__all__ = ["SearchVisibilityController", "SearchVisibilityHost"]
