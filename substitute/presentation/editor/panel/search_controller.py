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

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor

from substitute.application.editor_search import (
    EditorSearchResult,
    EditorSearchService,
    TextSearchMatch,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.presentation.editor.prompt_editor import PromptEditor


class SignalConnectorProtocol(Protocol):
    """Describe a Qt-like signal that accepts connected callbacks."""

    def connect(self, callback: Callable[[], None]) -> None:
        """Connect one callback to the signal."""


class SearchPromptEditorProtocol(Protocol):
    """Describe prompt editor APIs used by panel search ownership."""

    textChanged: SignalConnectorProtocol

    def property(self, name: str) -> object:
        """Return one dynamic Qt property."""

    def setProperty(self, name: str, value: object) -> object:
        """Set one dynamic Qt property."""

    def clear_search_matches(self) -> None:
        """Clear rendered text-search ranges."""


class NodeBehaviorServiceProtocol(Protocol):
    """Describe behavior snapshot construction used for search corpus snapshots."""

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
        """Build a behavior snapshot for the supplied search corpus inputs."""


class EditorPanelSearchHost(Protocol):
    """Describe panel state and facades needed by search ownership."""

    node_behavior_service: NodeBehaviorServiceProtocol
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
        self._current_node_search_text: str | None = None
        self._current_search_hidden_keys: set[object] = set()
        self._current_search_matching_nodes: set[tuple[str, str]] | None = None
        self._current_search_result: EditorSearchResult | None = None
        self._navigation = PanelSearchNavigationState(
            matches=(),
            index=-1,
            needle="",
        )
        self._text_search_refresh_pending = False
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

        return self._text_search_refresh_pending

    def configure_prompt_text_search_refresh(
        self,
        prompt_editor: SearchPromptEditorProtocol,
    ) -> None:
        """Attach active search recomputation to one prompt editor."""

        if prompt_editor.property("promptTextSearchRefreshTracked") is True:
            return
        prompt_editor.setProperty("promptTextSearchRefreshTracked", True)
        prompt_editor.textChanged.connect(
            lambda: self.schedule_text_search_refresh(prompt_editor)
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
        if prompt_editor is not None:
            prompt_editor.clear_search_matches()
        if self._text_search_refresh_pending:
            return
        self._text_search_refresh_pending = True
        self._publish_search_state()
        QTimer.singleShot(0, self.refresh_scheduled_text_search)

    def refresh_scheduled_text_search(self) -> None:
        """Recompute active editor text-search highlights from latest buffers."""

        self._text_search_refresh_pending = False
        self._publish_search_state()
        self.refresh_editor_search_result_after_text_change()

    def clear_search_filters(self) -> None:
        """Clear editor search state and reapply visibility without search filters."""

        self._current_node_search_text = None
        self._current_search_hidden_keys = set()
        self._current_search_matching_nodes = None
        self._current_search_result = None
        self._set_field_search_state(None, active=False)
        self.highlight_inputs_matching("")
        self._navigation = PanelSearchNavigationState(
            matches=(),
            index=-1,
            needle="",
        )
        self._publish_search_state()
        self._host.refresh_node_behavior_state(
            search_hidden_keys=set(),
            node_search_text=None,
            reason="search_changed",
        )

    def build_search_corpus_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Build an unfiltered snapshot used as the authoritative search corpus."""

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

    def highlight_inputs_matching(self, text: str) -> None:
        """Maintain backward-compatible highlight clearing for direct callers."""

        if text.strip():
            return
        self._clear_search_widget_state()
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
            self._clear_search_widget_state()
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
        selected_widget = self._host.input_widgets_by_field_key.get(
            (
                selected_match.cube_alias,
                selected_match.node_name,
                selected_match.field_key,
            )
        )
        if selected_widget is None:
            return

        set_focus = getattr(selected_widget, "setFocus", None)
        if callable(set_focus):
            set_focus()
        self._apply_selection_to_widget(selected_widget, selected_match)

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

        snapshot = self.build_search_corpus_snapshot()
        if snapshot is None:
            return

        active_match = self._current_navigation_match()
        result = EditorSearchService().build_result(snapshot, previous_result.query)
        self._apply_editor_search_result(
            result,
            preferred_match=active_match,
            select_current_match=False,
            update_visibility=False,
        )

    def editor_search_result_has_text_needle(self, result: EditorSearchResult) -> bool:
        """Return whether one search result owns source-text matches."""

        return bool(self._result_needle(result).strip())

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
            if self._match_widget_supports_navigation(match)
        )
        active_index = self._navigation_index_for_preferred_match(
            navigation_matches,
            preferred_match,
        )
        self._current_search_result = result
        self._navigation = PanelSearchNavigationState(
            matches=navigation_matches,
            index=active_index,
            needle=self._result_needle(result),
        )

        if update_visibility:
            self._apply_search_visibility_state(result)

        if select_current_match:
            self._clear_search_widget_state()
        else:
            self._clear_search_rendering_state()
        self._apply_all_text_search_state(result)
        self._publish_search_state()
        if navigation_matches and select_current_match:
            self._apply_current_navigation_match()

    def _apply_search_visibility_state(self, result: EditorSearchResult) -> None:
        """Apply node and field visibility filters for a newly submitted query."""

        if result.query.mode.value == "field":
            if result.query.tokens:
                self._current_node_search_text = None
                self._current_search_hidden_keys = set()
                self._current_search_matching_nodes = set(result.matching_nodes)
                self._set_field_search_state(result.matching_fields, active=True)
                self._publish_search_state()
                self._host.refresh_node_behavior_state(
                    search_hidden_keys=set(),
                    node_search_text=None,
                    search_matching_nodes=result.matching_nodes,
                    reason="search_changed",
                )
            else:
                self._clear_editor_visibility_filters()
        elif result.query.mode.value == "node":
            self._set_field_search_state(None, active=False)
            self._current_search_hidden_keys = set()
            self._current_node_search_text = None
            if result.query.node_filter_text:
                self._current_search_matching_nodes = set(result.matching_nodes)
                self._publish_search_state()
                self._host.refresh_node_behavior_state(
                    search_hidden_keys=set(),
                    node_search_text=None,
                    search_matching_nodes=result.matching_nodes,
                    reason="search_changed",
                )
            else:
                self._clear_editor_visibility_filters()
        else:
            self._set_field_search_state(None, active=False)
            self._clear_editor_visibility_filters()

    def _clear_editor_visibility_filters(self) -> None:
        """Clear node and field visibility filters without clearing text search."""

        self._current_node_search_text = None
        self._current_search_hidden_keys = set()
        self._current_search_matching_nodes = None
        self._set_field_search_state(None, active=False)
        self._publish_search_state()
        self._host.refresh_node_behavior_state(
            search_hidden_keys=set(),
            node_search_text=None,
            reason="search_changed",
        )

    def _clear_search_widget_state(self) -> None:
        """Clear transient line-edit and prompt-editor search rendering state."""

        seen_widgets: set[int] = set()
        for widget in self._host.input_widgets_by_field_key.values():
            widget_id = id(widget)
            if widget_id in seen_widgets:
                continue
            seen_widgets.add(widget_id)
            if isinstance(widget, PromptEditor):
                widget.clear_search_matches()
                cursor = widget.textCursor()
                cursor.clearSelection()
                widget.setTextCursor(cursor)
                continue
            deselect = getattr(widget, "deselect", None)
            if callable(deselect):
                deselect()

    def _clear_search_rendering_state(self) -> None:
        """Clear rendered search ranges without changing widget cursor positions."""

        seen_widgets: set[int] = set()
        for widget in self._host.input_widgets_by_field_key.values():
            widget_id = id(widget)
            if widget_id in seen_widgets:
                continue
            seen_widgets.add(widget_id)
            if isinstance(widget, PromptEditor):
                widget.clear_search_matches()

    def _set_field_search_state(
        self,
        match_keys: set[tuple[str, str, str]] | None,
        *,
        active: bool,
    ) -> None:
        """Apply field-search state through the current field-sync facade."""

        set_search_field_match_keys = getattr(
            self._host,
            "set_search_field_match_keys",
            None,
        )
        if callable(set_search_field_match_keys):
            set_search_field_match_keys(match_keys, active=active)

    def _apply_all_text_search_state(self, result: EditorSearchResult) -> None:
        """Apply prompt highlight ranges for every field with text matches."""

        matches_by_field: dict[tuple[str, str, str], list[TextSearchMatch]] = (
            defaultdict(list)
        )
        for match in result.text_matches:
            matches_by_field[
                (match.cube_alias, match.node_name, match.field_key)
            ].append(match)

        active_match = self._current_navigation_match()
        for field_key, matches in matches_by_field.items():
            widget = self._host.input_widgets_by_field_key.get(field_key)
            if not isinstance(widget, PromptEditor):
                continue
            active_index = None
            if (
                active_match is not None
                and (
                    active_match.cube_alias,
                    active_match.node_name,
                    active_match.field_key,
                )
                == field_key
            ):
                active_index = matches.index(active_match)
            widget.set_search_matches(
                tuple((match.start, match.length) for match in matches),
                active_index=active_index,
                query_identity=result.query,
            )

    def _apply_current_navigation_match(self) -> None:
        """Render and scroll to the current navigation match when one exists."""

        active_match = self._current_navigation_match()
        self._clear_search_widget_state()
        if isinstance(self._current_search_result, EditorSearchResult):
            self._apply_all_text_search_state(self._current_search_result)
        if active_match is None:
            return
        widget = self._host.input_widgets_by_field_key.get(
            (active_match.cube_alias, active_match.node_name, active_match.field_key)
        )
        if widget is None:
            return
        self._apply_selection_to_widget(widget, active_match)
        self._host.scroll_to_cube(active_match.cube_alias, animated=True)
        self._host.scroll_to_input_widget(widget, animated=True)

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

    @staticmethod
    def _apply_selection_to_widget(widget: object, match: TextSearchMatch) -> None:
        """Apply the active navigation selection to one searchable widget."""

        if isinstance(widget, PromptEditor):
            cursor = widget.textCursor()
            cursor.setPosition(match.start)
            cursor.movePosition(
                QTextCursor.MoveOperation.Right,
                QTextCursor.MoveMode.KeepAnchor,
                match.length,
            )
            widget.setTextCursor(cursor)
            return
        set_selection = getattr(widget, "setSelection", None)
        if callable(set_selection):
            set_selection(match.start, match.length)

    @staticmethod
    def _result_needle(result: EditorSearchResult) -> str:
        """Return the active text needle used by one search result."""

        if result.query.mode.value == "text":
            return result.query.normalized_text
        return result.query.text_filter_text

    def _match_widget_supports_navigation(self, match: TextSearchMatch) -> bool:
        """Return whether one text match maps to a navigable widget."""

        widget = self._host.input_widgets_by_field_key.get(
            (match.cube_alias, match.node_name, match.field_key)
        )
        if widget is None:
            return False
        return isinstance(widget, PromptEditor) or hasattr(widget, "setSelection")

    def _publish_search_state(self) -> None:
        """Mirror search state for adjacent owners not yet extracted."""

        self._host._current_node_search_text = self._current_node_search_text
        self._host._current_search_hidden_keys = set(self._current_search_hidden_keys)
        self._host._current_search_matching_nodes = (
            None
            if self._current_search_matching_nodes is None
            else set(self._current_search_matching_nodes)
        )
        self._host._current_search_result = self._current_search_result
        self._host._current_search = self._navigation.to_panel_dict()
        self._host._text_search_refresh_pending = self._text_search_refresh_pending


__all__ = [
    "EditorPanelSearchController",
    "EditorPanelSearchHost",
    "PanelSearchNavigationState",
    "SearchPromptEditorProtocol",
]
