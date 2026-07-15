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

"""Handle editor search orchestration for the workspace shell."""

from __future__ import annotations

from typing import Protocol

from substitute.application.editor_search import (
    EditorSearchMode,
    EditorSearchService,
)


class ContextSearchBoxProtocol(Protocol):
    """Describe floating search-box behavior used by search actions."""

    def context(self) -> str:
        """Return the active search context."""

    def searchText(self) -> str:
        """Return the current search text."""

    def set_navigation_enabled(self, enabled: bool) -> None:
        """Enable or disable next/previous navigation affordances."""


class EditorPanelSearchProtocol(Protocol):
    """Describe editor-panel search behavior used by search actions."""

    def build_search_corpus_snapshot(self) -> object:
        """Return the authoritative snapshot used by application-owned search."""

    def apply_search_result(self, result: object) -> None:
        """Apply one application-owned search result to the live panel."""

    def search_and_select(self, search_text: str, direction: str = "next") -> None:
        """Cycle through matching search results."""

    def highlight_inputs_matching(self, text: str) -> None:
        """Highlight prompt-editor matches."""

    def filter_node_cards_by_search(self, search_text: str) -> None:
        """Filter node cards using simple search behavior."""

    def refresh_node_behavior_state(
        self,
        *,
        search_hidden_keys: set[str] | None = None,
        node_search_text: str | None = None,
        reason: str = "search_changed",
    ) -> None:
        """Recompute node visibility state from search filters."""

    def clear_search_filters(self) -> None:
        """Clear all active search filters."""


class OverrideManagerProtocol(Protocol):
    """Describe override-manager behavior proxied by search actions."""

    def _on_override_menu_toggled(self, action: object) -> None:
        """Apply one override menu toggle."""


class WorkspaceSearchActionView(Protocol):
    """Describe the shell surface consumed by search actions."""

    active_editor_panel: EditorPanelSearchProtocol | None
    active_override_manager: OverrideManagerProtocol | None
    contextSearchBox: ContextSearchBoxProtocol

    def get_active_workflow(self) -> object:
        """Return the active workflow state."""


class WorkspaceSearchActions:
    """Own context-search and override-menu proxy behavior."""

    def __init__(self, view: WorkspaceSearchActionView) -> None:
        """Store the shell view dependency."""

        self._view = view
        self._search_service = EditorSearchService()

    def on_cycle_search_match(self) -> None:
        """Cycle to the next text-search match in the active editor panel."""

        view = self._view
        active_panel = view.active_editor_panel
        if active_panel is None:
            return

        if view.contextSearchBox.context() != "Field":
            active_panel.search_and_select(
                view.contextSearchBox.searchText(),
                direction="next",
            )

    def on_cycle_search_match_backward(self) -> None:
        """Cycle to the previous text-search match in the active editor panel."""

        view = self._view
        active_panel = view.active_editor_panel
        if active_panel is None:
            return

        if view.contextSearchBox.context() != "Field":
            active_panel.search_and_select(
                view.contextSearchBox.searchText(),
                direction="prev",
            )

    def on_context_search_changed(self, context: str, search_text: str) -> None:
        """Apply context-aware node, field, or text filtering to the active editor."""

        view = self._view
        active_panel = view.active_editor_panel
        if active_panel is None:
            return

        snapshot = active_panel.build_search_corpus_snapshot()
        if snapshot is None:
            return

        mode = self._search_mode_for_context(context)
        query = self._search_service.build_query(mode=mode, raw_text=search_text)
        result = self._search_service.build_result(snapshot, query)
        active_panel.apply_search_result(result)
        current_search = getattr(active_panel, "_current_search", {})
        view.contextSearchBox.set_navigation_enabled(
            bool(current_search.get("matches"))
        )

    def on_search_closed(self) -> None:
        """Clear node and field filters after the floating search box closes."""

        if self._view.active_editor_panel is not None:
            self._view.active_editor_panel.clear_search_filters()

    def proxy_override_menu_toggled(self, action: object) -> None:
        """Proxy override-menu toggles to the currently active override manager."""

        if self._view.active_override_manager is not None:
            self._view.active_override_manager._on_override_menu_toggled(action)

    @staticmethod
    def _search_mode_for_context(context: str) -> EditorSearchMode:
        """Map one shell context label onto the application search mode enum."""

        if context in ("Text", "Text boxes"):
            return EditorSearchMode.TEXT
        if context == "Field":
            return EditorSearchMode.FIELD
        return EditorSearchMode.NODE


__all__ = ["WorkspaceSearchActions", "WorkspaceSearchActionView"]
