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

"""Test source-backed public cursor adapter behavior."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.editing.cursor_state import (
    PromptCursorState,
)
from substitute.presentation.editor.prompt_editor.interactions.cursor_adapter import (
    PromptCursorAdapter,
)


class _CursorAdapterHost:
    """Provide deterministic source and cursor operations for adapter contracts."""

    KEEP_ANCHOR = object()

    def __init__(self, source_text: str, cursor_state: PromptCursorState) -> None:
        """Store initial source and cursor state."""

        self.source_text = source_text
        self.cursor_state = cursor_state
        self.finished_reasons: list[str] = []
        self.edit_block_depth = 0

    def cursor_adapter_source_text(self) -> str:
        """Return current source text."""

        return self.source_text

    def cursor_adapter_state(self) -> PromptCursorState:
        """Return current cursor state."""

        return self.cursor_state

    def cursor_adapter_commit_state(
        self,
        cursor_state: PromptCursorState,
        *,
        reason: str,
    ) -> PromptCursorState:
        """Commit a cursor state constrained by the current source text."""

        _ = reason
        self.cursor_state = cursor_state.clamped(len(self.source_text))
        return self.cursor_state

    def cursor_adapter_is_keep_anchor_mode(self, mode: object | None) -> bool:
        """Recognize the test keep-anchor sentinel."""

        return mode is self.KEEP_ANCHOR

    def cursor_adapter_finish_pending_key_edit_block(self, *, reason: str) -> None:
        """Record explicit cursor-command edit flushes."""

        self.finished_reasons.append(reason)

    def move_cursor_by_operation(
        self,
        operation: object,
        *,
        keep_anchor: bool,
    ) -> PromptCursorState:
        """Move one source position for the adapter protocol."""

        delta = 1 if operation == "right" else -1
        cursor_position = max(
            0,
            min(len(self.source_text), self.cursor_state.cursor_position + delta),
        )
        anchor_position = (
            self.cursor_state.anchor_position if keep_anchor else cursor_position
        )
        return self.cursor_adapter_commit_state(
            PromptCursorState(
                cursor_position=cursor_position,
                anchor_position=anchor_position,
            ),
            reason="move",
        )

    def cursor_adapter_begin_edit_block(self, *, finish_typing: bool = True) -> None:
        """Open one edit block."""

        _ = finish_typing
        self.edit_block_depth += 1

    def cursor_adapter_end_edit_block(self) -> None:
        """Close one edit block."""

        self.edit_block_depth -= 1

    def cursor_adapter_delete_selection(self) -> None:
        """Delete the selected source interval."""

        selection = self.cursor_state.selection()
        if selection.is_empty:
            return
        self.source_text = (
            self.source_text[: selection.start] + self.source_text[selection.end :]
        )
        self.cursor_adapter_commit_state(
            PromptCursorState(
                cursor_position=selection.start,
                anchor_position=selection.start,
            ),
            reason="delete",
        )

    def cursor_adapter_insert_text(self, text: str) -> None:
        """Replace the selected source interval with text."""

        selection = self.cursor_state.selection()
        self.source_text = (
            self.source_text[: selection.start]
            + text
            + self.source_text[selection.end :]
        )
        cursor_position = selection.start + len(text)
        self.cursor_adapter_commit_state(
            PromptCursorState(
                cursor_position=cursor_position,
                anchor_position=cursor_position,
            ),
            reason="insert",
        )

    def select_by_mode(self, mode: object) -> PromptCursorState:
        """Select the first source word for the adapter protocol."""

        _ = mode
        return self.cursor_adapter_commit_state(
            PromptCursorState(cursor_position=5, anchor_position=0),
            reason="select",
        )


def test_cursor_adapter_commits_position_and_preserves_keep_anchor() -> None:
    """Commit explicit positions through the host cursor boundary."""

    host = _CursorAdapterHost("alpha beta", PromptCursorState())
    cursor = PromptCursorAdapter(host)

    cursor.setPosition(2)
    cursor.setPosition(7, host.KEEP_ANCHOR)

    assert host.cursor_state == PromptCursorState(
        cursor_position=7,
        anchor_position=2,
    )
    assert cursor.selectionStart() == 2
    assert cursor.selectionEnd() == 7
    assert cursor.selectedText() == "pha b"
    assert host.finished_reasons == [
        "cursor_set_position",
        "cursor_set_position",
    ]


def test_cursor_adapter_insert_text_replaces_committed_selection() -> None:
    """Apply insertion after committing the adapter-owned selection."""

    host = _CursorAdapterHost(
        "alpha beta",
        PromptCursorState(cursor_position=5, anchor_position=0),
    )
    cursor = PromptCursorAdapter(host)

    cursor.insertText("omega")

    assert host.source_text == "omega beta"
    assert host.cursor_state == PromptCursorState(
        cursor_position=len("omega"),
        anchor_position=len("omega"),
    )
    assert cursor.position() == len("omega")


def test_cursor_adapter_clear_selection_collapses_to_active_cursor() -> None:
    """Preserve cursor direction while collapsing the adapter selection."""

    host = _CursorAdapterHost(
        "alpha beta",
        PromptCursorState(cursor_position=2, anchor_position=7),
    )
    cursor = PromptCursorAdapter(host)

    cursor.clearSelection()

    assert host.cursor_state == PromptCursorState(cursor_position=2, anchor_position=2)
    assert not cursor.hasSelection()
