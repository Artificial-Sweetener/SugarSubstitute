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

"""Tests for Phase 3.2 prompt editor clipboard and source commands."""

from __future__ import annotations

from typing import cast

from substitute.application.prompt_editor import PromptSourceNormalizationService
from substitute.presentation.editor.prompt_editor.commands import (
    PromptClipboardCommandResult,
    PromptCommandDispatcher,
    PromptCommandSourceRange,
    PromptCommandTextReplacement,
    PromptCopySelectionCommand,
    PromptCutSelectionCommand,
    PromptPasteTextCommand,
    PromptReplaceFullSourceCommand,
    PromptReplaceSourceRangeCommand,
    PromptSelectAllCommand,
    normalized_clipboard_paste_text,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)


def _session(
    source_text: str,
    *,
    cursor_position: int | None = None,
    anchor_position: int | None = None,
) -> PromptEditingSession[str]:
    """Return one editing session for command execution tests."""

    default_position = len(source_text)
    return PromptEditingSession(
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(
            cursor_position=(
                default_position if cursor_position is None else cursor_position
            ),
            anchor_position=default_position
            if anchor_position is None
            else anchor_position,
        ),
        max_undo_states=8,
        max_redo_states=8,
    )


def _undo_snapshot(session: PromptEditingSession[str]) -> PromptUndoSnapshot[str]:
    """Return the current session state as a passive undo snapshot."""

    return PromptUndoSnapshot(
        source_text=session.source_text,
        cursor_state=session.cursor_state,
        restoration_payload=session.source_text,
    )


def test_copy_selection_command_returns_source_backed_text_without_mutation() -> None:
    """Copy should report selected raw source text without changing source state."""

    session = _session("alpha beta", cursor_position=5, anchor_position=0)
    result = cast(
        PromptClipboardCommandResult[str],
        PromptCommandDispatcher(session).execute(PromptCopySelectionCommand()),
    )

    assert result.status == "completed"
    assert result.clipboard_text == "alpha"
    assert result.cursor_state == PromptCursorState(
        cursor_position=5,
        anchor_position=0,
    )
    assert session.source_text == "alpha beta"
    assert session.source_revision == 0


def test_cut_selection_command_returns_range_without_mutating_source() -> None:
    """Cut should prepare the selected source range and leave mutation to replace."""

    session = _session("alpha beta", cursor_position=5, anchor_position=0)
    result = cast(
        PromptClipboardCommandResult[str],
        PromptCommandDispatcher(session).execute(PromptCutSelectionCommand()),
    )

    assert result.status == "completed"
    assert result.clipboard_text == "alpha"
    assert result.source_range == PromptCommandSourceRange(start=0, end=5)
    assert result.replacement_text == ""
    assert session.source_text == "alpha beta"
    assert session.source_revision == 0


def test_cut_selection_command_noops_for_empty_selection() -> None:
    """Cut should not fabricate a source range when there is no selection."""

    session = _session("alpha", cursor_position=2, anchor_position=2)
    result = cast(
        PromptClipboardCommandResult[str],
        PromptCommandDispatcher(session).execute(PromptCutSelectionCommand()),
    )

    assert result.status == "noop"
    assert result.reason == "empty_selection"
    assert result.source_range is None
    assert result.clipboard_text is None
    assert session.source_text == "alpha"


def test_paste_text_command_returns_current_selection_range() -> None:
    """Paste should prepare selected source replacement without editing directly."""

    session = _session("alpha beta", cursor_position=10, anchor_position=6)
    result = cast(
        PromptClipboardCommandResult[str],
        PromptCommandDispatcher(session).execute(PromptPasteTextCommand("gamma")),
    )

    assert result.status == "completed"
    assert result.source_range == PromptCommandSourceRange(start=6, end=10)
    assert result.replacement_text == "gamma"
    assert session.source_text == "alpha beta"
    assert session.source_revision == 0


def test_select_all_command_updates_session_cursor_state() -> None:
    """Select-all should use the editing session as cursor authority."""

    session = _session("alpha")
    result = PromptCommandDispatcher(session).execute(PromptSelectAllCommand())

    assert result.status == "completed"
    assert result.cursor_state == PromptCursorState(
        cursor_position=5, anchor_position=0
    )
    assert session.cursor_state == result.cursor_state


def test_replace_source_range_command_normalizes_pasted_range() -> None:
    """Range replacement should use paste-range normalization when requested."""

    session = _session("alpha")
    result = PromptCommandDispatcher(session).execute(
        PromptReplaceSourceRangeCommand(
            name="paste_literal",
            replacement=PromptCommandTextReplacement(
                source_range=PromptCommandSourceRange(start=5, end=5),
                replacement_text=" (beta)",
                origin=PromptSourceEditOrigin.PASTE,
            ),
            normalizer=PromptSourceNormalizationService(),
            undo_snapshot=_undo_snapshot(session),
        )
    )

    assert result.status == "applied"
    assert session.source_text == "alpha (beta:1.10)"
    assert result.cursor_state == PromptCursorState(
        cursor_position=len("alpha (beta:1.10)"),
        anchor_position=len("alpha (beta:1.10)"),
    )
    assert session.can_undo()


def test_replace_source_range_command_reports_same_text_noop() -> None:
    """Same-text replacement should return a no-op command result with cursor state."""

    session = _session("alpha")
    result = PromptCommandDispatcher(session).execute(
        PromptReplaceSourceRangeCommand(
            name="same_text",
            replacement=PromptCommandTextReplacement(
                source_range=PromptCommandSourceRange(start=1, end=2),
                replacement_text="l",
                origin=PromptSourceEditOrigin.PROGRAMMATIC,
                exact_source=True,
            ),
            normalizer=PromptSourceNormalizationService(),
            undo_snapshot=_undo_snapshot(session),
        )
    )

    assert result.status == "noop"
    assert result.reason == "same_source"
    assert result.source_change is not None
    assert not result.source_change.source_changed
    assert result.cursor_state == PromptCursorState(
        cursor_position=2, anchor_position=2
    )
    assert session.source_text == "alpha"
    assert not session.can_undo()


def test_replace_full_source_command_preserves_exact_source_when_requested() -> None:
    """Full-source command should preserve literal text for exact-source edits."""

    session = _session("alpha")
    result = PromptCommandDispatcher(session).execute(
        PromptReplaceFullSourceCommand(
            name="replace_exact",
            text="literal (beta)",
            cursor_position=len("literal (beta)"),
            anchor_position=len("literal (beta)"),
            normalizer=PromptSourceNormalizationService(),
            exact_source=True,
            record_undo=True,
            clear_history=False,
            undo_snapshot=_undo_snapshot(session),
        )
    )

    assert result.status == "applied"
    assert session.source_text == "literal (beta)"
    assert session.can_undo()


def test_normalized_clipboard_paste_text_matches_exact_source_mode() -> None:
    """Paste normalization helper should mirror normal paste source behavior."""

    normalizer = PromptSourceNormalizationService()

    assert (
        normalized_clipboard_paste_text(
            "(literal)",
            normalizer=normalizer,
            exact_source=False,
        )
        == "(literal:1.10)"
    )
    assert (
        normalized_clipboard_paste_text(
            "(literal)",
            normalizer=normalizer,
            exact_source=True,
        )
        == "(literal)"
    )
