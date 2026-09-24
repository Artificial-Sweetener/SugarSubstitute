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

"""Build widget-independent editor search corpus snapshots and results."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from substitute.application.editor_search import EditorSearchResult, EditorSearchService
from substitute.application.node_behavior import EditorBehaviorSnapshot


class SearchSnapshotServiceProtocol(Protocol):
    """Describe behavior snapshot construction for a search corpus."""

    def build_snapshot(
        self,
        *,
        cube_states: Mapping[str, object],
        stack_order: list[str],
        workflow_overrides: Mapping[str, object],
        search_hidden_keys: set[object],
        node_search_text: str | None,
        search_matching_nodes: set[tuple[str, str]] | None,
    ) -> EditorBehaviorSnapshot:
        """Build a behavior snapshot for supplied unfiltered inputs."""


class SearchCorpusHost(Protocol):
    """Describe live state required to capture an unfiltered search corpus."""

    node_behavior_service: SearchSnapshotServiceProtocol
    _cube_states: Mapping[str, object] | None
    _stack_order: list[str] | None

    def _workflow_overrides(self) -> Mapping[str, object]:
        """Return active workflow overrides."""


class EditorSearchCorpus:
    """Build search results from behavior snapshots without touching widgets."""

    def __init__(self, host: SearchCorpusHost) -> None:
        """Store the live corpus inputs."""

        self._host = host

    def snapshot(self) -> EditorBehaviorSnapshot | None:
        """Build an unfiltered authoritative search corpus snapshot."""

        if not self._host._stack_order or not self._host._cube_states:
            return None
        return self._host.node_behavior_service.build_snapshot(
            cube_states=self._host._cube_states,
            stack_order=list(self._host._stack_order),
            workflow_overrides=self._host._workflow_overrides(),
            search_hidden_keys=set(),
            node_search_text=None,
            search_matching_nodes=None,
        )

    def rebuild(self, previous_result: EditorSearchResult) -> EditorSearchResult | None:
        """Rebuild one result from current source text and its existing query."""

        snapshot = self.snapshot()
        if snapshot is None:
            return None
        return EditorSearchService().build_result(snapshot, previous_result.query)

    @staticmethod
    def result_needle(result: EditorSearchResult) -> str:
        """Return the active text needle used by one search result."""

        if result.query.mode.value == "text":
            return result.query.normalized_text
        return result.query.text_filter_text


__all__ = ["EditorSearchCorpus", "SearchCorpusHost"]
