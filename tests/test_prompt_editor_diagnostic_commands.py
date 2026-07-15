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

"""Tests for Phase 3.4 prompt editor diagnostic commands."""

from __future__ import annotations

from typing import cast

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptDuplicateSegmentDiagnosticPayload,
    PromptSourceNormalizationService,
    PromptSpellingDiagnosticPayload,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptAddSpellingDiagnosticToDictionaryCommand,
    PromptCommandDispatcher,
    PromptCommandSourceIdentity,
    PromptDiagnosticCommandResult,
    PromptDuplicateEmphasisDiagnosticAction,
    PromptDuplicateIgnoreDiagnosticAction,
    PromptDuplicateRemovalDiagnosticAction,
    PromptEmphasizeFirstDuplicateDiagnosticCommand,
    PromptIgnoreDuplicateDiagnosticCommand,
    PromptIgnoreSpellingDiagnosticCommand,
    PromptRemoveDuplicateDiagnosticCommand,
    PromptReplaceSpellingDiagnosticCommand,
    PromptSpellingDictionaryAddDiagnosticAction,
    PromptSpellingIgnoreDiagnosticAction,
    PromptSpellingReplacementDiagnosticAction,
    build_diagnostic_action_command,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
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
    """Return one editing session for diagnostic command tests."""

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


def _source_identity(
    session: PromptEditingSession[str],
) -> PromptCommandSourceIdentity:
    """Return the current source identity for stale-command tests."""

    return PromptCommandSourceIdentity(
        source_revision=session.source_revision,
        source_length=len(session.source_text),
    )


def test_spelling_replacement_command_replaces_exact_diagnostic_range() -> None:
    """Spelling replacement should edit only the diagnostic source range."""

    session = _session("one typo ", cursor_position=len("one typo "))
    result = cast(
        PromptDiagnosticCommandResult[str],
        PromptCommandDispatcher(session).execute(
            PromptReplaceSpellingDiagnosticCommand(
                action=PromptSpellingReplacementDiagnosticAction(
                    diagnostic=_spelling_diagnostic(4, 8, "typo"),
                    replacement_text="type",
                    source_identity=_source_identity(session),
                ),
                normalizer=PromptSourceNormalizationService(),
                exact_source=False,
                undo_snapshot=_undo_snapshot(session),
            )
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "one type "
    assert len(result.source_changes) == 1
    assert result.cursor_state == PromptCursorState(
        cursor_position=8,
        anchor_position=8,
    )
    assert session.can_undo()


def test_spelling_replacement_command_rejects_stale_identity() -> None:
    """Spelling replacement should fail closed when source identity changed."""

    session = _session("one typo ")
    command = build_diagnostic_action_command(
        PromptSpellingReplacementDiagnosticAction(
            diagnostic=_spelling_diagnostic(4, 8, "typo"),
            replacement_text="type",
            source_identity=PromptCommandSourceIdentity(
                source_revision=session.source_revision + 1,
                source_length=len(session.source_text),
            ),
        ),
        normalizer=PromptSourceNormalizationService(),
        exact_source=False,
        undo_snapshot=_undo_snapshot(session),
    )

    result = PromptCommandDispatcher(session).execute(command)

    assert result.status == "rejected"
    assert result.reason == "stale_source"
    assert session.source_text == "one typo "
    assert not session.can_undo()


def test_spelling_replacement_command_rejects_range_text_mismatch() -> None:
    """Spelling replacement should not edit when the diagnostic word moved."""

    moved_session = _session("one type ")
    mismatch_result = PromptCommandDispatcher(moved_session).execute(
        PromptReplaceSpellingDiagnosticCommand(
            action=PromptSpellingReplacementDiagnosticAction(
                diagnostic=_spelling_diagnostic(4, 8, "typo"),
                replacement_text="type",
            ),
            normalizer=PromptSourceNormalizationService(),
            exact_source=False,
            undo_snapshot=_undo_snapshot(moved_session),
        )
    )

    assert mismatch_result.status == "rejected"
    assert mismatch_result.reason == "diagnostic_source_mismatch"
    assert moved_session.source_text == "one type "


def test_duplicate_removal_command_removes_duplicate_segment() -> None:
    """Duplicate removal should apply the application-owned removal edits."""

    session = _session("alpha, beta, beta")
    diagnostic = _duplicate_diagnostic(
        normalized_segment="beta",
        first_start=7,
        first_end=11,
        duplicate_start=13,
        duplicate_end=17,
    )
    result = cast(
        PromptDiagnosticCommandResult[str],
        PromptCommandDispatcher(session).execute(
            PromptRemoveDuplicateDiagnosticCommand(
                action=PromptDuplicateRemovalDiagnosticAction(
                    diagnostic=diagnostic,
                    source_identity=_source_identity(session),
                ),
                normalizer=PromptSourceNormalizationService(),
                exact_source=False,
                undo_snapshot=_undo_snapshot(session),
            )
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "alpha, beta"
    assert len(result.source_changes) == 1


def test_duplicate_emphasis_command_removes_duplicate_and_emphasizes_first() -> None:
    """Duplicate emphasis should apply both edits from right to left."""

    session = _session("yellow hat, yellow hat")
    diagnostic = _duplicate_diagnostic(
        normalized_segment="yellow hat",
        first_start=0,
        first_end=10,
        duplicate_start=12,
        duplicate_end=22,
    )
    result = cast(
        PromptDiagnosticCommandResult[str],
        PromptCommandDispatcher(session).execute(
            PromptEmphasizeFirstDuplicateDiagnosticCommand(
                action=PromptDuplicateEmphasisDiagnosticAction(
                    diagnostic=diagnostic,
                    source_identity=_source_identity(session),
                ),
                normalizer=PromptSourceNormalizationService(),
                exact_source=False,
                undo_snapshot=_undo_snapshot(session),
            )
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "(yellow hat:1.10)"
    assert len(result.source_changes) == 2


def test_duplicate_command_rejects_payload_range_mismatch() -> None:
    """Duplicate commands should reject diagnostics that disagree with payload ranges."""

    session = _session("alpha, beta, beta")
    diagnostic = PromptDiagnostic(
        diagnostic_id="duplicate:13:17:beta",
        kind=PromptDiagnosticKind.DUPLICATE_SEGMENT,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=7,
        source_end=11,
        message="Duplicate prompt segment: beta",
        payload=PromptDuplicateSegmentDiagnosticPayload(
            normalized_segment="beta",
            first_source_start=7,
            first_source_end=11,
            duplicate_source_start=13,
            duplicate_source_end=17,
        ),
    )

    result = PromptCommandDispatcher(session).execute(
        PromptRemoveDuplicateDiagnosticCommand(
            action=PromptDuplicateRemovalDiagnosticAction(diagnostic=diagnostic),
            normalizer=PromptSourceNormalizationService(),
            exact_source=False,
            undo_snapshot=_undo_snapshot(session),
        )
    )

    assert result.status == "rejected"
    assert result.reason == "diagnostic_payload_mismatch"
    assert session.source_text == "alpha, beta, beta"


def test_spelling_ignore_and_dictionary_commands_return_validated_word() -> None:
    """Non-mutating spelling commands should expose the validated spelling word."""

    session = _session("one typo ")
    diagnostic = _spelling_diagnostic(4, 8, "typo")

    ignore_result = cast(
        PromptDiagnosticCommandResult[str],
        PromptCommandDispatcher(session).execute(
            PromptIgnoreSpellingDiagnosticCommand(
                PromptSpellingIgnoreDiagnosticAction(
                    diagnostic=diagnostic,
                    source_identity=_source_identity(session),
                )
            )
        ),
    )
    add_result = cast(
        PromptDiagnosticCommandResult[str],
        PromptCommandDispatcher(session).execute(
            PromptAddSpellingDiagnosticToDictionaryCommand(
                PromptSpellingDictionaryAddDiagnosticAction(
                    diagnostic=diagnostic,
                    source_identity=_source_identity(session),
                )
            )
        ),
    )

    assert ignore_result.status == "completed"
    assert ignore_result.spelling_word == "typo"
    assert add_result.status == "completed"
    assert add_result.spelling_word == "typo"
    assert session.source_text == "one typo "
    assert not session.can_undo()


def test_duplicate_ignore_command_returns_validated_diagnostic_id() -> None:
    """Non-mutating duplicate ignore should expose the validated diagnostic id."""

    session = _session("alpha, beta, beta")
    diagnostic = _duplicate_diagnostic(
        normalized_segment="beta",
        first_start=7,
        first_end=11,
        duplicate_start=13,
        duplicate_end=17,
    )

    result = cast(
        PromptDiagnosticCommandResult[str],
        PromptCommandDispatcher(session).execute(
            PromptIgnoreDuplicateDiagnosticCommand(
                PromptDuplicateIgnoreDiagnosticAction(
                    diagnostic=diagnostic,
                    source_identity=_source_identity(session),
                )
            )
        ),
    )

    assert result.status == "completed"
    assert result.ignored_diagnostic_id == diagnostic.diagnostic_id
    assert session.source_text == "alpha, beta, beta"
    assert not session.can_undo()


def _spelling_diagnostic(
    source_start: int,
    source_end: int,
    word: str,
) -> PromptDiagnostic:
    """Return one deterministic spelling diagnostic."""

    return PromptDiagnostic(
        diagnostic_id=f"spelling:{source_start}:{source_end}:{word}",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=source_start,
        source_end=source_end,
        message=f"Possible spelling issue: {word}",
        payload=PromptSpellingDiagnosticPayload(word=word),
    )


def _duplicate_diagnostic(
    *,
    normalized_segment: str,
    first_start: int,
    first_end: int,
    duplicate_start: int,
    duplicate_end: int,
) -> PromptDiagnostic:
    """Return one deterministic duplicate-segment diagnostic."""

    return PromptDiagnostic(
        diagnostic_id=f"duplicate:{duplicate_start}:{duplicate_end}:{normalized_segment}",
        kind=PromptDiagnosticKind.DUPLICATE_SEGMENT,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=duplicate_start,
        source_end=duplicate_end,
        message=f"Duplicate prompt segment: {normalized_segment}",
        payload=PromptDuplicateSegmentDiagnosticPayload(
            normalized_segment=normalized_segment,
            first_source_start=first_start,
            first_source_end=first_end,
            duplicate_source_start=duplicate_start,
            duplicate_source_end=duplicate_end,
        ),
    )
