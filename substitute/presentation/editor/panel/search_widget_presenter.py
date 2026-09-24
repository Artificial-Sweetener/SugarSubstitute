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

"""Present editor search highlights, selection, focus, and reveal on widgets."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Protocol

from PySide6.QtGui import QTextCursor

from substitute.application.editor_search import EditorSearchResult, TextSearchMatch
from substitute.presentation.editor.prompt_editor import PromptEditor


class SearchWidgetHost(Protocol):
    """Describe mounted widgets and reveal commands used by search presentation."""

    input_widgets_by_field_key: Mapping[tuple[str, str, str], object]

    def scroll_to_cube(self, cube_alias: str, *, animated: bool = True) -> None:
        """Scroll the panel to one cube alias."""

    def scroll_to_input_widget(self, widget: object, *, animated: bool = True) -> None:
        """Scroll the panel to one input widget."""


class SearchWidgetPresenter:
    """Render search state without owning queries or navigation policy."""

    def __init__(self, host: SearchWidgetHost) -> None:
        """Store the mounted widget lookup and reveal commands."""

        self._host = host

    def clear_widget_state(self) -> None:
        """Clear transient highlights and active text selection."""

        seen_widgets: set[int] = set()
        for widget in self._host.input_widgets_by_field_key.values():
            if id(widget) in seen_widgets:
                continue
            seen_widgets.add(id(widget))
            if isinstance(widget, PromptEditor):
                widget.clear_search_matches()
                cursor = widget.textCursor()
                cursor.clearSelection()
                widget.setTextCursor(cursor)
                continue
            deselect = getattr(widget, "deselect", None)
            if callable(deselect):
                deselect()

    def clear_rendering_state(self) -> None:
        """Clear rendered prompt ranges without moving cursors."""

        seen_widgets: set[int] = set()
        for widget in self._host.input_widgets_by_field_key.values():
            if id(widget) in seen_widgets:
                continue
            seen_widgets.add(id(widget))
            if isinstance(widget, PromptEditor):
                widget.clear_search_matches()

    def apply_text_matches(
        self,
        result: EditorSearchResult,
        active_match: TextSearchMatch | None,
    ) -> None:
        """Apply all prompt highlight ranges and their active index."""

        matches_by_field: dict[tuple[str, str, str], list[TextSearchMatch]] = (
            defaultdict(list)
        )
        for match in result.text_matches:
            matches_by_field[
                (match.cube_alias, match.node_name, match.field_key)
            ].append(match)
        for field_key, matches in matches_by_field.items():
            widget = self._host.input_widgets_by_field_key.get(field_key)
            if not isinstance(widget, PromptEditor):
                continue
            active_index = None
            if active_match is not None and active_match in matches:
                active_index = matches.index(active_match)
            widget.set_search_matches(
                tuple((match.start, match.length) for match in matches),
                active_index=active_index,
                query_identity=result.query,
            )

    def focus(self, match: TextSearchMatch) -> None:
        """Focus and select one match when its widget is mounted."""

        widget = self._widget_for_match(match)
        if widget is None:
            return
        set_focus = getattr(widget, "setFocus", None)
        if callable(set_focus):
            set_focus()
        self.apply_selection(widget, match)

    def reveal(self, match: TextSearchMatch) -> None:
        """Select and scroll to one mounted search match."""

        widget = self._widget_for_match(match)
        if widget is None:
            return
        self.apply_selection(widget, match)
        self._host.scroll_to_cube(match.cube_alias, animated=True)
        self._host.scroll_to_input_widget(widget, animated=True)

    def supports_navigation(self, match: TextSearchMatch) -> bool:
        """Return whether one text match maps to a selectable widget."""

        widget = self._widget_for_match(match)
        return widget is not None and (
            isinstance(widget, PromptEditor) or hasattr(widget, "setSelection")
        )

    @staticmethod
    def apply_selection(widget: object, match: TextSearchMatch) -> None:
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

    def _widget_for_match(self, match: TextSearchMatch) -> object | None:
        """Return the mounted widget for one semantic match identity."""

        return self._host.input_widgets_by_field_key.get(
            (match.cube_alias, match.node_name, match.field_key)
        )


__all__ = ["SearchWidgetHost", "SearchWidgetPresenter"]
