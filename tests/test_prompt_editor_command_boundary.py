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

"""Tests for the prompt editor command ownership boundary."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from substitute.application.prompt_editor import PromptSourceNormalizationService
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandDispatcher,
    PromptCommandResult,
    PromptCommandSourceIdentity,
    PromptCommandSourceRange,
    PromptCommandTextReplacement,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)


def _undo_snapshot(source_text: str) -> PromptUndoSnapshot[str]:
    """Return a passive undo snapshot for command-boundary tests."""

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
    """Return one editing session for deterministic command execution."""

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


@dataclass(frozen=True, slots=True)
class _ReplaceRangeCommand:
    """Apply one prepared source replacement through the editing session."""

    name: str
    replacement: PromptCommandTextReplacement

    def execute(
        self,
        session: PromptEditingSession[str],
    ) -> PromptCommandResult[str]:
        """Execute the replacement against the supplied editing session."""

        source_change = session.replace_source_range(
            start=self.replacement.source_range.start,
            end=self.replacement.source_range.end,
            replacement_text=self.replacement.replacement_text,
            normalizer=PromptSourceNormalizationService(),
            origin=self.replacement.origin,
            exact_source=self.replacement.exact_source,
            record_undo=self.replacement.record_undo,
            undo_snapshot=_undo_snapshot(session.source_text),
        )
        if not source_change.source_changed:
            return PromptCommandResult.noop(
                self.name,
                cursor_state=source_change.cursor_state,
                reason="same_source",
            )
        return PromptCommandResult.applied(self.name, source_change)


@dataclass(frozen=True, slots=True)
class _RejectedCommand:
    """Reject one stale prepared command without touching the session."""

    name: str
    reason: str

    def execute(
        self,
        session: PromptEditingSession[str],
    ) -> PromptCommandResult[str]:
        """Return a rejected result without reading mutable widget state."""

        _ = session
        return PromptCommandResult.rejected(self.name, reason=self.reason)


def test_dispatcher_executes_command_through_editing_session() -> None:
    """The command dispatcher should apply mutations through the session owner."""

    session = _session("alpha")
    dispatcher = PromptCommandDispatcher(session)
    command = _ReplaceRangeCommand(
        name="append_text",
        replacement=PromptCommandTextReplacement(
            source_range=PromptCommandSourceRange(start=5, end=5),
            replacement_text=" beta",
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
            exact_source=True,
        ),
    )

    result = dispatcher.execute(command)

    assert result.status == "applied"
    assert result.command_name == "append_text"
    assert result.source_change is not None
    assert result.source_change.source_changed
    assert result.cursor_state == PromptCursorState(
        cursor_position=len("alpha beta"),
        anchor_position=len("alpha beta"),
    )
    assert session.source_text == "alpha beta"
    assert session.can_undo()


def test_noop_command_result_can_update_cursor_without_revision_bump() -> None:
    """A command can report a no-op source edit while preserving cursor output."""

    session = _session("alpha")
    dispatcher = PromptCommandDispatcher(session)
    command = _ReplaceRangeCommand(
        name="same_text",
        replacement=PromptCommandTextReplacement(
            source_range=PromptCommandSourceRange(start=1, end=2),
            replacement_text="l",
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
            exact_source=True,
        ),
    )

    result = dispatcher.execute(command)

    assert result.status == "noop"
    assert result.reason == "same_source"
    assert result.source_change is None
    assert result.cursor_state == PromptCursorState(
        cursor_position=2,
        anchor_position=2,
    )
    assert session.source_text == "alpha"
    assert session.source_revision == 0
    assert not session.can_undo()


def test_rejected_command_result_does_not_mutate_session() -> None:
    """Rejected prepared commands should be deterministic and side-effect free."""

    session = _session("alpha")
    dispatcher = PromptCommandDispatcher(session)

    result = dispatcher.execute(
        _RejectedCommand(name="stale_autocomplete_accept", reason="stale_source")
    )

    assert result == PromptCommandResult[str].rejected(
        "stale_autocomplete_accept",
        reason="stale_source",
    )
    assert session.source_text == "alpha"
    assert session.source_revision == 0
    assert not session.can_undo()


def test_source_identity_matches_revision_and_optional_length() -> None:
    """Prepared command source identity should reject stale source snapshots."""

    identity = PromptCommandSourceIdentity(source_revision=3, source_length=12)

    assert identity.matches(source_revision=3, source_length=12)
    assert not identity.matches(source_revision=4, source_length=12)
    assert not identity.matches(source_revision=3, source_length=11)
    assert identity.matches(source_revision=3)


def test_source_range_validation_rejects_invalid_prepared_ranges() -> None:
    """Prepared source range values should fail before command execution."""

    with pytest.raises(ValueError, match="non-negative"):
        PromptCommandSourceRange(start=-1, end=0)
    with pytest.raises(ValueError, match="must not precede"):
        PromptCommandSourceRange(start=2, end=1)

    source_range = PromptCommandSourceRange(start=2, end=5)
    assert source_range.length == 3
    assert not source_range.is_empty
    assert source_range.is_within(5)
    assert not source_range.is_within(4)
