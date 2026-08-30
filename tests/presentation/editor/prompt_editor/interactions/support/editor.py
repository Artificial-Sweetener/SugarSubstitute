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

"""Provide editor and cursor doubles for prompt interaction tests."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

from substitute.application.prompt_editor.document.views import PromptSyntaxSpanView
from substitute.application.prompt_editor.reorder.commit import (
    PromptReorderLayoutCommitRequest,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptEmphasisAdjustmentSession,
    PromptTransientNeutralEmphasisOwner,
)


class MenuSelectionDouble:
    """Expose the minimal Qt selection API used by controller tests."""

    def __init__(self, cursor: MenuCursorDouble) -> None:
        """Store the cursor backing this selection."""

        self._cursor = cursor

    def isEmpty(self) -> bool:  # noqa: N802
        """Return whether the tracked selection is empty."""

        return self._cursor.selectionStart() == self._cursor.selectionEnd()


class MenuCursorDouble:
    """Provide the minimal cursor API used by reorder controller tests."""

    def __init__(
        self,
        *,
        text: str,
        position: int,
        anchor: int | None = None,
    ) -> None:
        """Store the backing text and cursor anchors."""

        self._text = text
        self._position = position
        self._anchor = position if anchor is None else anchor
        self.moves: list[tuple[int, object | None]] = []

    def sync_text(self, text: str) -> None:
        """Replace the backing text used for selection slices."""

        self._text = text

    def position(self) -> int:
        """Return the current cursor position."""

        return self._position

    def anchor(self) -> int:
        """Return the current cursor anchor."""

        return self._anchor

    def selection(self) -> MenuSelectionDouble:
        """Return the current selection wrapper."""

        return MenuSelectionDouble(self)

    def selectionStart(self) -> int:  # noqa: N802
        """Return the inclusive selection start."""

        return min(self._anchor, self._position)

    def selectionEnd(self) -> int:  # noqa: N802
        """Return the exclusive selection end."""

        return max(self._anchor, self._position)

    def selectedText(self) -> str:  # noqa: N802
        """Return the selected source substring."""

        return self._text[self.selectionStart() : self.selectionEnd()]

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether the cursor tracks a non-empty selection."""

        return self.selectionStart() != self.selectionEnd()

    def setPosition(self, pos: int, mode: object | None = None) -> None:  # noqa: N802
        """Move or extend the tracked cursor selection."""

        self.moves.append((pos, mode))
        mode_name = "" if mode is None else str(mode)
        if mode == "keep" or mode_name.endswith("KeepAnchor"):
            self._position = pos
            return
        self._anchor = pos
        self._position = pos


class ControllerEditorDouble:
    """Provide the editor API required by reorder interaction tests."""

    def __init__(
        self,
        *,
        clicked_cursor: MenuCursorDouble,
        current_cursor: MenuCursorDouble,
        text: str,
        parent_widget: object | None = None,
        viewport: object | None = None,
    ) -> None:
        """Store cursors and prompt text used by the controller."""

        self._clicked_cursor = clicked_cursor
        self._current_cursor = current_cursor
        self._text = text
        self._parent_widget = parent_widget
        self._viewport = (
            viewport
            if viewport is not None
            else SimpleNamespace(
                mapToGlobal=lambda position: position,
                width=lambda: 0,
            )
        )
        self.reorder_preview_state_calls: list[object | None] = []
        self.clear_reorder_preview_state_calls = 0
        self.autocomplete_preview_state_calls: list[object | None] = []
        self.has_pending_projection_update_result = False
        self.flush_pending_projection_update_calls: list[str] = []
        self._reorder_preview_state: object | None = None
        self.clear_emphasis_adjustment_session_calls = 0
        self.executed_reorder_requests: list[PromptReorderLayoutCommitRequest] = []
        self._source_publication_callback: Callable[[], None] | None = None

    def cursorForPosition(self, _pos: object) -> MenuCursorDouble:  # noqa: N802
        """Return the clicked cursor at the menu position."""

        return self._clicked_cursor

    def textCursor(self) -> MenuCursorDouble:  # noqa: N802
        """Return the current editor cursor."""

        return self._current_cursor

    def setTextCursor(self, cursor: MenuCursorDouble) -> None:  # noqa: N802
        """Persist the supplied cursor."""

        cursor.sync_text(self._text)
        self._current_cursor = cursor

    def toPlainText(self) -> str:  # noqa: N802
        """Return the backing prompt text."""

        return self._text

    def setPlainText(self, text: str) -> None:  # noqa: N802
        """Replace the backing prompt text and synchronize cursors."""

        self._text = text
        self._clicked_cursor.sync_text(text)
        self._current_cursor.sync_text(text)
        if self._source_publication_callback is not None:
            self._source_publication_callback()

    def bind_source_publication(self, callback: Callable[[], None]) -> None:
        """Bind the production-equivalent source publication boundary."""

        self._source_publication_callback = callback

    def prompt_command_source_identity(self) -> PromptSourceIdentity | None:
        """Return no source identity for direct controller tests."""

        return None

    def active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return no editor-owned active syntax span."""

        return None

    def viewport(self) -> object:
        """Return the editor viewport used by overlay positioning code."""

        return self._viewport

    def parentWidget(self) -> object | None:  # noqa: N802
        """Return the configured parent widget."""

        return self._parent_widget

    def mapFromGlobal(self, position: object) -> object:  # noqa: N802
        """Return the supplied global position unchanged."""

        return position

    def setFocus(self) -> None:  # noqa: N802
        """Accept focus restoration requests."""

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return no active emphasis-adjustment session."""

        return None

    def clear_emphasis_adjustment_session(self) -> None:
        """Record one emphasis session clear request."""

        self.clear_emphasis_adjustment_session_calls += 1

    def clear_transient_neutral_emphasis(self) -> None:
        """Accept transient neutral emphasis clears."""

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return no active transient neutral emphasis owner."""

        return None

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return no active transient neutral emphasis range."""

        return None

    def set_reorder_preview_state(self, preview_state: object | None) -> None:
        """Record explicit reorder preview state pushes."""

        self._reorder_preview_state = preview_state
        self.reorder_preview_state_calls.append(preview_state)

    def clear_reorder_preview_state(self) -> None:
        """Record preview-state clear requests."""

        self._reorder_preview_state = None
        self.clear_reorder_preview_state_calls += 1

    def set_autocomplete_preview_state(self, preview_state: object | None) -> None:
        """Record autocomplete preview updates."""

        self.autocomplete_preview_state_calls.append(preview_state)

    def has_pending_projection_update(self) -> bool:
        """Return whether a projection update is pending."""

        return self.has_pending_projection_update_result

    def flush_pending_projection_update(self, *, reason: str) -> None:
        """Record pending projection flushes."""

        self.flush_pending_projection_update_calls.append(reason)
        self.has_pending_projection_update_result = False

    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        **_kwargs: object,
    ) -> object:
        """Record unexpected reorder command execution."""

        self.executed_reorder_requests.append(request)
        raise AssertionError("This reorder interaction test should not mutate source.")
