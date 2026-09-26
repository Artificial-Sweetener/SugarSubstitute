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

"""Own editor-panel search state, refresh scheduling, and result navigation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from PySide6.QtCore import QObject

from substitute.application.editor_search import (
    EditorSearchResult,
    TextSearchMatch,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot

from .search_corpus import EditorSearchCorpus, SearchCorpusHost
from .search_refresh_scheduler import SearchPromptEditorProtocol, SearchRefreshScheduler
from .search_visibility_controller import (
    SearchVisibilityController,
    SearchVisibilityHost,
)
from .search_widget_presenter import SearchWidgetHost, SearchWidgetPresenter


class EditorPanelSearchHost(Protocol):
    """Describe panel state and facades needed by search ownership."""

    input_widgets_by_field_key: Mapping[tuple[str, str, str], object]
    _cube_states: Mapping[str, object] | None
    _stack_order: list[str] | None
    _current_node_search_text: str | None
    _current_search_hidden_keys: set[object]
    _current_search_matching_nodes: set[tuple[str, str]] | None
    _current_search_result: EditorSearchResult | None
    _current_search: dict[str, object]
    _text_search_refresh_pending: bool

    def _workflow_overrides(self) -> Mapping[str, object]:
        """Return workflow overrides used by behavior snapshots."""

    def refresh_node_behavior_state(
        self,
        search_hidden_keys: set[object] | None = None,
        node_search_text: str | None = None,
        search_matching_nodes: set[tuple[str, str]] | None = None,
        *,
        reason: str = "search_changed",
    ) -> None:
        """Refresh panel behavior visibility for search state."""

    def set_search_field_match_keys(
        self,
        match_keys: set[tuple[str, str, str]] | None,
        *,
        active: bool,
    ) -> None:
        """Publish field-search match keys to hidden-field ownership."""

    def scroll_to_cube(self, cube_alias: str, *, animated: bool = True) -> None:
        """Scroll the panel to one cube alias."""

    def scroll_to_input_widget(self, widget: object, *, animated: bool = True) -> None:
        """Scroll the panel to one input widget."""


@dataclass(frozen=True, slots=True)
class PanelSearchNavigationState:
    """Capture active text-search navigation state for shell consumers."""

    matches: tuple[TextSearchMatch, ...]
    index: int
    needle: str

    def to_panel_dict(self) -> dict[str, object]:
        """Return the legacy panel dictionary shape consumed by shell code."""

        return {
            "matches": self.matches,
            "index": self.index,
            "needle": self.needle,
        }


class EditorPanelSearchController:
    """Coordinate panel search filters, text highlights, and navigation."""

    def __init__(self, host: EditorPanelSearchHost) -> None:
        """Store host and publish default mirrored search state."""

        self._host = host
        self._current_search_result: EditorSearchResult | None = None
        self._navigation = PanelSearchNavigationState(
            matches=(),
            index=-1,
            needle="",
        )
        self._corpus = EditorSearchCorpus(cast(SearchCorpusHost, host))
        self._widgets = SearchWidgetPresenter(cast(SearchWidgetHost, host))
        self._visibility = SearchVisibilityController(cast(SearchVisibilityHost, host))
        self._refresh_scheduler = SearchRefreshScheduler(
            on_pending_changed=self._publish_refresh_pending,
            on_refresh=self.refresh_editor_search_result_after_text_change,
            lifetime_owner=cast(QObject, host),
        )
        self._publish_search_state()

    @property
    def current_search_result(self) -> EditorSearchResult | None:
        """Return the active application-owned search result."""

        return self._current_search_result

    @property
    def navigation_state(self) -> PanelSearchNavigationState:
        """Return the active panel search navigation state."""

        return self._navigation

    @property
    def text_search_refresh_pending(self) -> bool:
        """Return whether a text-search refresh is queued."""

        return self._refresh_scheduler.pending

    def configure_prompt_text_search_refresh(
        self,
        prompt_editor: SearchPromptEditorProtocol,
    ) -> None:
        """Attach active search recomputation to one prompt editor."""

        self._refresh_scheduler.configure(
            prompt_editor,
            self.schedule_text_search_refresh,
        )

    def schedule_text_search_refresh(
        self,
        prompt_editor: SearchPromptEditorProtocol | None = None,
    ) -> None:
        """Schedule active text-search ranges to be rebuilt after prompt edits."""

        if not isinstance(self._current_search_result, EditorSearchResult):
            return
        if not self.editor_search_result_has_text_needle(self._current_search_result):
            return
        self._refresh_scheduler.schedule(prompt_editor)

    def clear_search_filters(self) -> None:
        """Clear editor search state and reapply visibility without search filters."""

        self._current_search_result = None
        self.highlight_inputs_matching("")
        self._navigation = PanelSearchNavigationState(
            matches=(),
            index=-1,
            needle="",
        )
        self._publish_search_state()
        self._visibility.clear()

    def build_search_corpus_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Build an unfiltered snapshot used as the authoritative search corpus."""

        return self._corpus.snapshot()

    def highlight_inputs_matching(self, text: str) -> None:
        """Maintain backward-compatible highlight clearing for direct callers."""

        if text.strip():
            return
        self._widgets.clear_widget_state()
        self._navigation = PanelSearchNavigationState(
            matches=(),
            index=-1,
            needle="",
        )
        self._publish_search_state()

    def filter_node_cards_by_search(self, search_text: str) -> None:
        """Delegate node-card filtering to the unified behavior snapshot path."""

        self._host.refresh_node_behavior_state(
            node_search_text=search_text.strip() or None,
            reason="search_changed",
        )

    def search_and_select(
        self,
        search_text: str,
        *,
        direction: str = "next",
    ) -> None:
        """Cycle already-computed text-search matches for the active result."""

        if not search_text.strip():
            self._widgets.clear_widget_state()
            self._navigation = PanelSearchNavigationState(
                matches=(),
                index=-1,
                needle="",
            )
            self._publish_search_state()
            return

        needle = search_text.lower().strip()
        if not self._navigation.matches or self._navigation.needle != needle:
            self._navigation = PanelSearchNavigationState(
                matches=self._navigation.matches,
                index=-1,
                needle=needle,
            )
            self._publish_search_state()
            return

        current_index = self._navigation.index
        if direction == "prev":
            current_index = (current_index - 1 + len(self._navigation.matches)) % len(
                self._navigation.matches
            )
        else:
            current_index = (current_index + 1) % len(self._navigation.matches)
        self._navigation = PanelSearchNavigationState(
            matches=self._navigation.matches,
            index=current_index,
            needle=needle,
        )
        self._publish_search_state()
        self._apply_current_navigation_match()

    def focus_current_search_match(self) -> None:
        """Focus the selected editor search match and clear global highlights."""

        matches = self._navigation.matches
        index = self._navigation.index
        if not matches:
            return
        if index < 0:
            index = 0
            self._navigation = PanelSearchNavigationState(
                matches=matches,
                index=index,
                needle=self._navigation.needle,
            )
            self._publish_search_state()
        selected_match = matches[index]
        self._widgets.focus(selected_match)

    def apply_search_result(self, result: EditorSearchResult) -> None:
        """Apply one application-owned search result to live widget state."""

        self._apply_editor_search_result(
            result,
            preferred_match=None,
            select_current_match=True,
            update_visibility=True,
        )

    def refresh_editor_search_result_after_text_change(self) -> None:
        """Recompute active text-search ranges after an editable field changes."""

        previous_result = self._current_search_result
        if not isinstance(previous_result, EditorSearchResult):
            return
        if not self.editor_search_result_has_text_needle(previous_result):
            return

        result = self._corpus.rebuild(previous_result)
        if result is None:
            return

        active_match = self._current_navigation_match()
        self._apply_editor_search_result(
            result,
            preferred_match=active_match,
            select_current_match=False,
            update_visibility=False,
        )

    def editor_search_result_has_text_needle(self, result: EditorSearchResult) -> bool:
        """Return whether one search result owns source-text matches."""

        return bool(self._corpus.result_needle(result).strip())

    def _apply_editor_search_result(
        self,
        result: EditorSearchResult,
        *,
        preferred_match: TextSearchMatch | None,
        select_current_match: bool,
        update_visibility: bool,
    ) -> None:
        """Apply one search result while optionally preserving active selection."""

        navigation_matches = tuple(
            match
            for match in result.navigation_matches
            if self._widgets.supports_navigation(match)
        )
        active_index = self._navigation_index_for_preferred_match(
            navigation_matches,
            preferred_match,
        )
        self._current_search_result = result
        self._navigation = PanelSearchNavigationState(
            matches=navigation_matches,
            index=active_index,
            needle=self._corpus.result_needle(result),
        )

        if update_visibility:
            self._visibility.apply(result)

        if select_current_match:
            self._widgets.clear_widget_state()
        else:
            self._widgets.clear_rendering_state()
        self._widgets.apply_text_matches(result, self._current_navigation_match())
        self._publish_search_state()
        if navigation_matches and select_current_match:
            self._apply_current_navigation_match()

    def _apply_current_navigation_match(self) -> None:
        """Render and scroll to the current navigation match when one exists."""

        active_match = self._current_navigation_match()
        self._widgets.clear_widget_state()
        if isinstance(self._current_search_result, EditorSearchResult):
            self._widgets.apply_text_matches(self._current_search_result, active_match)
        if active_match is None:
            return
        self._widgets.reveal(active_match)

    def _current_navigation_match(self) -> TextSearchMatch | None:
        """Return the currently selected navigation match for active search."""

        matches = self._navigation.matches
        if not matches:
            return None
        index = self._navigation.index
        if index < 0 or index >= len(matches):
            return None
        return matches[index]

    @staticmethod
    def _navigation_index_for_preferred_match(
        navigation_matches: tuple[TextSearchMatch, ...],
        preferred_match: TextSearchMatch | None,
    ) -> int:
        """Return the navigation index that best preserves active match intent."""

        if not navigation_matches:
            return -1
        if preferred_match is None:
            return 0
        for index, match in enumerate(navigation_matches):
            if match == preferred_match:
                return index
        same_field_matches = tuple(
            (index, match)
            for index, match in enumerate(navigation_matches)
            if (
                match.cube_alias,
                match.node_name,
                match.field_key,
            )
            == (
                preferred_match.cube_alias,
                preferred_match.node_name,
                preferred_match.field_key,
            )
        )
        if not same_field_matches:
            return 0
        nearest_index, _nearest_match = min(
            same_field_matches,
            key=lambda item: abs(item[1].start - preferred_match.start),
        )
        return nearest_index

    def _publish_refresh_pending(self, _pending: bool) -> None:
        """Publish scheduler state through the transitional panel mirror."""

        self._publish_search_state()

    def _publish_search_state(self) -> None:
        """Mirror search state for adjacent owners not yet extracted."""

        self._visibility.publish()
        self._host._current_search_result = self._current_search_result
        self._host._current_search = self._navigation.to_panel_dict()
        self._host._text_search_refresh_pending = self._refresh_scheduler.pending


__all__ = [
    "EditorPanelSearchController",
    "EditorPanelSearchHost",
    "PanelSearchNavigationState",
]
