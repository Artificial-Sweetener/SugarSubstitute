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

"""Define diagnostic action commands for prompt editing."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar, cast

from substitute.application.prompt_editor.diagnostics.duplicate_mutations import (
    PromptDiagnosticTextEdit,
    emphasize_first_duplicate_segment_edits,
    remove_duplicate_segment_edits,
)
from substitute.application.prompt_editor.diagnostics.models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDuplicateSegmentDiagnosticPayload,
    PromptSpellingDiagnosticPayload,
)
from ..core.editing.commands import PromptReplaceRangeEdit
from ..core.editing.session import PromptEditingSession
from ..core.editing.source_commands import (
    PromptSourceEditOrigin,
    PromptSourceNormalizer,
    source_text_edit_between,
)
from ..core.editing.transactions import PromptUndoSnapshot

from .contracts import PromptCommandResult
from .execution import PromptEditExecution

TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class PromptSpellingReplacementDiagnosticAction:
    """Describe one prepared spelling replacement diagnostic action."""

    diagnostic: PromptDiagnostic
    replacement_text: str
    source_identity: PromptSourceIdentity | None = None


@dataclass(frozen=True, slots=True)
class PromptSpellingIgnoreDiagnosticAction:
    """Describe one prepared session-scoped spelling ignore action."""

    diagnostic: PromptDiagnostic
    source_identity: PromptSourceIdentity | None = None


@dataclass(frozen=True, slots=True)
class PromptSpellingDictionaryAddDiagnosticAction:
    """Describe one prepared persistent spelling dictionary action."""

    diagnostic: PromptDiagnostic
    source_identity: PromptSourceIdentity | None = None


@dataclass(frozen=True, slots=True)
class PromptDuplicateRemovalDiagnosticAction:
    """Describe one prepared duplicate-segment removal action."""

    diagnostic: PromptDiagnostic
    source_identity: PromptSourceIdentity | None = None


@dataclass(frozen=True, slots=True)
class PromptDuplicateEmphasisDiagnosticAction:
    """Describe one prepared duplicate-segment emphasis transfer action."""

    diagnostic: PromptDiagnostic
    source_identity: PromptSourceIdentity | None = None


@dataclass(frozen=True, slots=True)
class PromptDuplicateIgnoreDiagnosticAction:
    """Describe one prepared session-scoped duplicate ignore action."""

    diagnostic: PromptDiagnostic
    source_identity: PromptSourceIdentity | None = None


PromptDiagnosticAction: TypeAlias = (
    PromptSpellingReplacementDiagnosticAction
    | PromptSpellingIgnoreDiagnosticAction
    | PromptSpellingDictionaryAddDiagnosticAction
    | PromptDuplicateRemovalDiagnosticAction
    | PromptDuplicateEmphasisDiagnosticAction
    | PromptDuplicateIgnoreDiagnosticAction
)


@dataclass(frozen=True, slots=True)
class PromptDiagnosticCommandResult(PromptCommandResult[TPayload]):
    """Report diagnostic command output for source and non-source actions."""

    spelling_word: str | None = None
    ignored_diagnostic_id: str | None = None


class PromptDiagnosticCommandService(Generic[TPayload]):
    """Execute diagnostic actions as one grouped editing transaction."""

    def __init__(
        self,
        *,
        execution: PromptEditExecution[TPayload],
        normalizer: PromptSourceNormalizer,
        exact_source_enabled: Callable[[], bool],
    ) -> None:
        """Store diagnostic command dependencies."""

        self._execution = execution
        self._normalizer = normalizer
        self._exact_source_enabled = exact_source_enabled

    def execute(
        self,
        action: PromptDiagnosticAction,
    ) -> PromptDiagnosticCommandResult[TPayload]:
        """Commit one prepared diagnostic action."""

        command = build_diagnostic_action_command(
            action,
            normalizer=self._normalizer,
            exact_source=self._exact_source_enabled(),
            undo_snapshot=self._execution.current_undo_snapshot(),
        )
        self._execution.finish_pending_key_edit_block(reason="diagnostic_action")
        self._execution.begin_edit_block(finish_typing=False)
        try:
            return cast(
                PromptDiagnosticCommandResult[TPayload],
                self._execution.execute(command),
            )
        finally:
            self._execution.end_edit_block()


@dataclass(frozen=True, slots=True)
class PromptReplaceSpellingDiagnosticCommand(Generic[TPayload]):
    """Replace one validated spelling diagnostic range."""

    action: PromptSpellingReplacementDiagnosticAction
    normalizer: PromptSourceNormalizer
    exact_source: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]
    name: str = "replace_spelling_diagnostic"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptDiagnosticCommandResult[TPayload]:
        """Apply this spelling replacement through the supplied session."""

        validation = _validate_spelling_diagnostic_action(
            command_name=self.name,
            session=session,
            diagnostic=self.action.diagnostic,
            source_identity=self.action.source_identity,
        )
        if validation is not None:
            return validation
        return _execute_diagnostic_text_edits(
            command_name=self.name,
            session=session,
            edits=(
                PromptDiagnosticTextEdit(
                    source_start=self.action.diagnostic.source_start,
                    source_end=self.action.diagnostic.source_end,
                    replacement_text=self.action.replacement_text,
                ),
            ),
            normalizer=self.normalizer,
            exact_source=self.exact_source,
            undo_snapshot=self.undo_snapshot,
        )


@dataclass(frozen=True, slots=True)
class PromptIgnoreSpellingDiagnosticCommand(Generic[TPayload]):
    """Validate one session-scoped spelling ignore action."""

    action: PromptSpellingIgnoreDiagnosticAction
    name: str = "ignore_spelling_diagnostic"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptDiagnosticCommandResult[TPayload]:
        """Return the validated spelling word that should be ignored."""

        validation = _validate_spelling_diagnostic_action(
            command_name=self.name,
            session=session,
            diagnostic=self.action.diagnostic,
            source_identity=self.action.source_identity,
        )
        if validation is not None:
            return validation
        payload = self.action.diagnostic.payload
        if not isinstance(payload, PromptSpellingDiagnosticPayload):
            return _rejected(self.name, "invalid_diagnostic_payload")
        return PromptDiagnosticCommandResult(
            command_name=self.name,
            status="completed",
            cursor_state=session.cursor_state,
            spelling_word=payload.word,
        )


@dataclass(frozen=True, slots=True)
class PromptAddSpellingDiagnosticToDictionaryCommand(Generic[TPayload]):
    """Validate one persistent spelling dictionary action."""

    action: PromptSpellingDictionaryAddDiagnosticAction
    name: str = "add_spelling_diagnostic_to_dictionary"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptDiagnosticCommandResult[TPayload]:
        """Return the validated spelling word that should be added."""

        validation = _validate_spelling_diagnostic_action(
            command_name=self.name,
            session=session,
            diagnostic=self.action.diagnostic,
            source_identity=self.action.source_identity,
        )
        if validation is not None:
            return validation
        payload = self.action.diagnostic.payload
        if not isinstance(payload, PromptSpellingDiagnosticPayload):
            return _rejected(self.name, "invalid_diagnostic_payload")
        return PromptDiagnosticCommandResult(
            command_name=self.name,
            status="completed",
            cursor_state=session.cursor_state,
            spelling_word=payload.word,
        )


@dataclass(frozen=True, slots=True)
class PromptRemoveDuplicateDiagnosticCommand(Generic[TPayload]):
    """Remove one validated duplicate-segment diagnostic occurrence."""

    action: PromptDuplicateRemovalDiagnosticAction
    normalizer: PromptSourceNormalizer
    exact_source: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]
    name: str = "remove_duplicate_diagnostic"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptDiagnosticCommandResult[TPayload]:
        """Apply this duplicate removal through the supplied session."""

        validation = _validate_duplicate_diagnostic_action(
            command_name=self.name,
            session=session,
            diagnostic=self.action.diagnostic,
            source_identity=self.action.source_identity,
        )
        if validation is not None:
            return validation
        payload = self.action.diagnostic.payload
        if not isinstance(payload, PromptDuplicateSegmentDiagnosticPayload):
            return _rejected(self.name, "invalid_diagnostic_payload")
        return _execute_diagnostic_text_edits(
            command_name=self.name,
            session=session,
            edits=remove_duplicate_segment_edits(session.source_text, payload),
            normalizer=self.normalizer,
            exact_source=self.exact_source,
            undo_snapshot=self.undo_snapshot,
        )


@dataclass(frozen=True, slots=True)
class PromptEmphasizeFirstDuplicateDiagnosticCommand(Generic[TPayload]):
    """Remove a duplicate occurrence and emphasize its first occurrence."""

    action: PromptDuplicateEmphasisDiagnosticAction
    normalizer: PromptSourceNormalizer
    exact_source: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]
    name: str = "emphasize_first_duplicate_diagnostic"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptDiagnosticCommandResult[TPayload]:
        """Apply this duplicate emphasis action through the supplied session."""

        validation = _validate_duplicate_diagnostic_action(
            command_name=self.name,
            session=session,
            diagnostic=self.action.diagnostic,
            source_identity=self.action.source_identity,
        )
        if validation is not None:
            return validation
        payload = self.action.diagnostic.payload
        if not isinstance(payload, PromptDuplicateSegmentDiagnosticPayload):
            return _rejected(self.name, "invalid_diagnostic_payload")
        return _execute_diagnostic_text_edits(
            command_name=self.name,
            session=session,
            edits=emphasize_first_duplicate_segment_edits(
                session.source_text,
                payload,
            ),
            normalizer=self.normalizer,
            exact_source=self.exact_source,
            undo_snapshot=self.undo_snapshot,
        )


@dataclass(frozen=True, slots=True)
class PromptIgnoreDuplicateDiagnosticCommand(Generic[TPayload]):
    """Validate one session-scoped duplicate diagnostic ignore action."""

    action: PromptDuplicateIgnoreDiagnosticAction
    name: str = "ignore_duplicate_diagnostic"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptDiagnosticCommandResult[TPayload]:
        """Return the validated duplicate diagnostic id to ignore."""

        validation = _validate_duplicate_diagnostic_action(
            command_name=self.name,
            session=session,
            diagnostic=self.action.diagnostic,
            source_identity=self.action.source_identity,
        )
        if validation is not None:
            return validation
        return PromptDiagnosticCommandResult(
            command_name=self.name,
            status="completed",
            cursor_state=session.cursor_state,
            ignored_diagnostic_id=self.action.diagnostic.diagnostic_id,
        )


def build_diagnostic_action_command(
    action: PromptDiagnosticAction,
    *,
    normalizer: PromptSourceNormalizer,
    exact_source: bool,
    undo_snapshot: PromptUndoSnapshot[TPayload],
) -> (
    PromptReplaceSpellingDiagnosticCommand[TPayload]
    | PromptIgnoreSpellingDiagnosticCommand[TPayload]
    | PromptAddSpellingDiagnosticToDictionaryCommand[TPayload]
    | PromptRemoveDuplicateDiagnosticCommand[TPayload]
    | PromptEmphasizeFirstDuplicateDiagnosticCommand[TPayload]
    | PromptIgnoreDuplicateDiagnosticCommand[TPayload]
):
    """Return the executable command for one prepared diagnostic action."""

    if isinstance(action, PromptSpellingReplacementDiagnosticAction):
        return PromptReplaceSpellingDiagnosticCommand(
            action=action,
            normalizer=normalizer,
            exact_source=exact_source,
            undo_snapshot=undo_snapshot,
        )
    if isinstance(action, PromptSpellingIgnoreDiagnosticAction):
        return PromptIgnoreSpellingDiagnosticCommand(action=action)
    if isinstance(action, PromptSpellingDictionaryAddDiagnosticAction):
        return PromptAddSpellingDiagnosticToDictionaryCommand(action=action)
    if isinstance(action, PromptDuplicateRemovalDiagnosticAction):
        return PromptRemoveDuplicateDiagnosticCommand(
            action=action,
            normalizer=normalizer,
            exact_source=exact_source,
            undo_snapshot=undo_snapshot,
        )
    if isinstance(action, PromptDuplicateEmphasisDiagnosticAction):
        return PromptEmphasizeFirstDuplicateDiagnosticCommand(
            action=action,
            normalizer=normalizer,
            exact_source=exact_source,
            undo_snapshot=undo_snapshot,
        )
    return PromptIgnoreDuplicateDiagnosticCommand(action=action)


def _validate_spelling_diagnostic_action(
    *,
    command_name: str,
    session: PromptEditingSession[TPayload],
    diagnostic: PromptDiagnostic,
    source_identity: PromptSourceIdentity | None,
) -> PromptDiagnosticCommandResult[TPayload] | None:
    """Return a rejection when a spelling diagnostic no longer matches source."""

    stale_result = _stale_result(
        command_name=command_name,
        session=session,
        source_identity=source_identity,
    )
    if stale_result is not None:
        return stale_result
    if diagnostic.kind is not PromptDiagnosticKind.SPELLING:
        return _rejected(command_name, "invalid_diagnostic_kind")
    payload = diagnostic.payload
    if not isinstance(payload, PromptSpellingDiagnosticPayload):
        return _rejected(command_name, "invalid_diagnostic_payload")
    if not _range_within_source(
        start=diagnostic.source_start,
        end=diagnostic.source_end,
        source_text=session.source_text,
    ):
        return _rejected(command_name, "invalid_source_range")
    if session.source_text[diagnostic.source_start : diagnostic.source_end] != (
        payload.word
    ):
        return _rejected(command_name, "diagnostic_source_mismatch")
    return None


def _validate_duplicate_diagnostic_action(
    *,
    command_name: str,
    session: PromptEditingSession[TPayload],
    diagnostic: PromptDiagnostic,
    source_identity: PromptSourceIdentity | None,
) -> PromptDiagnosticCommandResult[TPayload] | None:
    """Return a rejection when a duplicate diagnostic no longer matches source."""

    stale_result = _stale_result(
        command_name=command_name,
        session=session,
        source_identity=source_identity,
    )
    if stale_result is not None:
        return stale_result
    if diagnostic.kind is not PromptDiagnosticKind.DUPLICATE_SEGMENT:
        return _rejected(command_name, "invalid_diagnostic_kind")
    payload = diagnostic.payload
    if not isinstance(payload, PromptDuplicateSegmentDiagnosticPayload):
        return _rejected(command_name, "invalid_diagnostic_payload")
    if (
        diagnostic.source_start != payload.duplicate_source_start
        or diagnostic.source_end != payload.duplicate_source_end
    ):
        return _rejected(command_name, "diagnostic_payload_mismatch")
    ranges = (
        (payload.first_source_start, payload.first_source_end),
        (payload.duplicate_source_start, payload.duplicate_source_end),
    )
    if any(
        not _range_within_source(start=start, end=end, source_text=session.source_text)
        for start, end in ranges
    ):
        return _rejected(command_name, "invalid_source_range")
    return None


def _stale_result(
    *,
    command_name: str,
    session: PromptEditingSession[TPayload],
    source_identity: PromptSourceIdentity | None,
) -> PromptDiagnosticCommandResult[TPayload] | None:
    """Return a stale rejection for a mismatched prepared source identity."""

    if source_identity is None:
        return None
    if source_identity.matches(
        source_revision=session.source_revision,
        source_length=len(session.source_text),
    ):
        return None
    return _rejected(command_name, "stale_source")


def _execute_diagnostic_text_edits(
    *,
    command_name: str,
    session: PromptEditingSession[TPayload],
    edits: tuple[PromptDiagnosticTextEdit, ...],
    normalizer: PromptSourceNormalizer,
    exact_source: bool,
    undo_snapshot: PromptUndoSnapshot[TPayload],
) -> PromptDiagnosticCommandResult[TPayload]:
    """Apply prepared diagnostic source edits from right to left."""

    if not edits:
        return PromptDiagnosticCommandResult(
            command_name=command_name,
            status="noop",
            cursor_state=session.cursor_state,
            reason="empty_edits",
        )
    for edit in edits:
        if not _range_within_source(
            start=edit.source_start,
            end=edit.source_end,
            source_text=session.source_text,
        ):
            return _rejected(command_name, "invalid_source_range")

    previous_source_text = session.source_text
    next_source_text = previous_source_text
    cursor_position = session.cursor_position
    for edit in sorted(edits, key=lambda item: item.source_start, reverse=True):
        next_source_text = (
            next_source_text[: edit.source_start]
            + edit.replacement_text
            + next_source_text[edit.source_end :]
        )
        cursor_position = edit.source_start + len(edit.replacement_text)
    combined_edit = source_text_edit_between(previous_source_text, next_source_text)
    if combined_edit is None:
        return PromptDiagnosticCommandResult(
            command_name=command_name,
            status="noop",
            cursor_state=session.cursor_state,
            reason="same_source",
        )
    edit_commit = session.execute(
        PromptReplaceRangeEdit(
            start=combined_edit.start,
            end=combined_edit.end,
            replacement_text=combined_edit.replacement_text,
            normalizer=normalizer,
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
            exact_source=exact_source,
            record_undo=True,
            undo_snapshot=undo_snapshot,
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        )
    )
    return PromptDiagnosticCommandResult(
        command_name=command_name,
        status="applied" if edit_commit.source_changed else "noop",
        edit_commit=edit_commit,
        cursor_state=edit_commit.cursor_state,
        undo_availability_change=edit_commit.undo_availability_change,
        reason=None if edit_commit.source_changed else "same_source",
    )


def _range_within_source(*, start: int, end: int, source_text: str) -> bool:
    """Return whether one source range is valid for source text."""

    return start >= 0 and start <= end <= len(source_text)


def _rejected(
    command_name: str,
    reason: str,
) -> PromptDiagnosticCommandResult[TPayload]:
    """Build a typed diagnostic command rejection."""

    return PromptDiagnosticCommandResult(
        command_name=command_name,
        status="rejected",
        reason=reason,
    )


__all__ = [
    "PromptAddSpellingDiagnosticToDictionaryCommand",
    "PromptDiagnosticAction",
    "PromptDiagnosticCommandResult",
    "PromptDiagnosticCommandService",
    "PromptDuplicateEmphasisDiagnosticAction",
    "PromptDuplicateIgnoreDiagnosticAction",
    "PromptDuplicateRemovalDiagnosticAction",
    "PromptEmphasizeFirstDuplicateDiagnosticCommand",
    "PromptIgnoreDuplicateDiagnosticCommand",
    "PromptIgnoreSpellingDiagnosticCommand",
    "PromptRemoveDuplicateDiagnosticCommand",
    "PromptReplaceSpellingDiagnosticCommand",
    "PromptSpellingDictionaryAddDiagnosticAction",
    "PromptSpellingIgnoreDiagnosticAction",
    "PromptSpellingReplacementDiagnosticAction",
    "build_diagnostic_action_command",
]
