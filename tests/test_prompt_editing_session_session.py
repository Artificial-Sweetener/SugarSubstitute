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

"""Tests for the prompt editing-session facade."""

from __future__ import annotations

from substitute.application.prompt_editor import PromptSourceNormalizationService
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)


def _undo_snapshot(source_text: str) -> PromptUndoSnapshot[str]:
    """Return one passive undo snapshot for facade tests."""

    cursor_position = len(source_text)
    return PromptUndoSnapshot(
        source_text=source_text,
        cursor_state=PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        ),
        restoration_payload=source_text,
    )


def _session(source_text: str = "") -> PromptEditingSession[str]:
    """Return an editing session with bounded undo history."""

    return PromptEditingSession(
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(
            cursor_position=len(source_text),
            anchor_position=len(source_text),
        ),
        max_undo_states=8,
        max_redo_states=8,
    )


def test_replace_full_source_updates_source_cursor_and_undo() -> None:
    """Full replacement should update all editing-session state owners."""

    session = _session()

    result = session.replace_full_source(
        "alpha",
        cursor_position=len("alpha"),
        anchor_position=len("alpha"),
        normalizer=PromptSourceNormalizationService(),
        exact_source=True,
        record_undo=True,
        clear_history=False,
        undo_snapshot=_undo_snapshot(""),
    )

    assert session.source_text == "alpha"
    assert session.source_revision == 1
    assert session.cursor_state == PromptCursorState(
        cursor_position=5,
        anchor_position=5,
    )
    assert result.cursor_state == session.cursor_state
    assert session.can_undo()


def test_replace_range_updates_cursor_and_revision_once() -> None:
    """Range replacement should return the applied source revision and cursor."""

    session = _session("alpha")

    result = session.replace_source_range(
        start=5,
        end=5,
        replacement_text=" beta",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_undo_snapshot("alpha"),
    )

    assert result.previous_snapshot.source_text == "alpha"
    assert result.next_snapshot.source_text == "alpha beta"
    assert result.next_snapshot.source_revision == session.source_revision == 1
    assert session.cursor_state == PromptCursorState(
        cursor_position=len("alpha beta"),
        anchor_position=len("alpha beta"),
    )


def test_noop_range_edit_updates_cursor_without_revision_bump() -> None:
    """No-op source edits should still commit cursor output."""

    session = PromptEditingSession[str](
        source_text="abc",
        source_revision=3,
        cursor_state=PromptCursorState(cursor_position=0, anchor_position=0),
        max_undo_states=8,
        max_redo_states=8,
    )

    result = session.replace_source_range(
        start=1,
        end=2,
        replacement_text="b",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_undo_snapshot("abc"),
    )

    assert not result.source_changed
    assert session.source_revision == 3
    assert session.cursor_state == PromptCursorState(
        cursor_position=2,
        anchor_position=2,
    )
    assert not session.can_undo()


def test_undo_and_redo_restore_source_and_cursor() -> None:
    """Undo and redo should restore source and cursor through the facade."""

    session = _session("alpha")
    session.replace_source_range(
        start=5,
        end=5,
        replacement_text=" beta",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_undo_snapshot("alpha"),
    )

    undo_result = session.undo(_undo_snapshot("alpha beta"))
    assert undo_result is not None
    assert session.source_text == "alpha"
    assert session.cursor_state == PromptCursorState(
        cursor_position=5,
        anchor_position=5,
    )
    assert undo_result.source_snapshot.source_revision == session.source_revision
    assert session.can_redo()

    redo_result = session.redo(_undo_snapshot("alpha"))
    assert redo_result is not None
    assert session.source_text == "alpha beta"
    assert session.cursor_state == PromptCursorState(
        cursor_position=len("alpha beta"),
        anchor_position=len("alpha beta"),
    )


def test_select_all_and_clipboard_intents_use_session_selection() -> None:
    """Cursor selection and clipboard intents should share one session owner."""

    session = _session("alpha beta")

    assert session.select_all() == PromptCursorState(
        cursor_position=len("alpha beta"),
        anchor_position=0,
    )
    assert session.copy().text == "alpha beta"
    cut_result = session.cut()
    assert cut_result is not None
    assert (cut_result.start, cut_result.end, cut_result.text) == (
        0,
        len("alpha beta"),
        "alpha beta",
    )
    paste_result = session.paste("omega")
    assert (paste_result.start, paste_result.end, paste_result.text) == (
        0,
        len("alpha beta"),
        "omega",
    )
