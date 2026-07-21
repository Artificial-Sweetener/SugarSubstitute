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

"""Define undo-safe prompt editor command boundary types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar

from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptCursorState,
    PromptEditingSession,
    PromptEditingSessionSourceChange,
    PromptSourceEditOrigin,
    PromptUndoAvailabilityChange,
)

TPayload = TypeVar("TPayload")

PromptCommandStatus = Literal["applied", "completed", "noop", "rejected"]


@dataclass(frozen=True, slots=True)
class PromptCommandSourceIdentity:
    """Identify prepared command input against the source snapshot that produced it."""

    source_revision: int
    source_length: int | None = None

    def __post_init__(self) -> None:
        """Reject invalid source identities before commands trust them."""

        if self.source_revision < 0:
            raise ValueError("Source revision must be non-negative.")
        if self.source_length is not None and self.source_length < 0:
            raise ValueError("Source length must be non-negative.")

    def matches(
        self, *, source_revision: int, source_length: int | None = None
    ) -> bool:
        """Return whether this identity still matches the supplied source state."""

        if self.source_revision != source_revision:
            return False
        if self.source_length is None or source_length is None:
            return True
        return self.source_length == source_length


@dataclass(frozen=True, slots=True)
class PromptCommandSourceRange:
    """Describe a half-open source range used by prepared command requests."""

    start: int
    end: int

    def __post_init__(self) -> None:
        """Reject invalid ranges before command execution mutates source."""

        if self.start < 0:
            raise ValueError("Source range start must be non-negative.")
        if self.end < self.start:
            raise ValueError("Source range end must not precede start.")

    @property
    def length(self) -> int:
        """Return the number of source characters covered by this range."""

        return self.end - self.start

    @property
    def is_empty(self) -> bool:
        """Return whether this range covers no source characters."""

        return self.start == self.end

    def is_within(self, source_length: int) -> bool:
        """Return whether this range is valid for one source length."""

        if source_length < 0:
            raise ValueError("Source length must be non-negative.")
        return self.end <= source_length


@dataclass(frozen=True, slots=True)
class PromptCommandTextReplacement:
    """Describe one prepared replacement that a command can apply through a session."""

    source_range: PromptCommandSourceRange
    replacement_text: str
    origin: PromptSourceEditOrigin
    exact_source: bool = False
    record_undo: bool = True
    cursor_position: int | None = None
    anchor_position: int | None = None


@dataclass(frozen=True, slots=True)
class PromptCommandResult(Generic[TPayload]):
    """Report the deterministic outcome of one prompt editor command."""

    command_name: str
    status: PromptCommandStatus
    source_change: PromptEditingSessionSourceChange[TPayload] | None = None
    cursor_state: PromptCursorState | None = None
    undo_availability_change: PromptUndoAvailabilityChange | None = None
    reason: str | None = None

    @classmethod
    def applied(
        cls,
        command_name: str,
        source_change: PromptEditingSessionSourceChange[TPayload],
    ) -> "PromptCommandResult[TPayload]":
        """Build a result for a command that applied one editing-session change."""

        return cls(
            command_name=command_name,
            status="applied",
            source_change=source_change,
            cursor_state=source_change.cursor_state,
            undo_availability_change=source_change.undo_availability_change,
        )

    @classmethod
    def from_source_change(
        cls,
        command_name: str,
        source_change: PromptEditingSessionSourceChange[TPayload],
        *,
        noop_reason: str = "same_source",
    ) -> "PromptCommandResult[TPayload]":
        """Build a result from an editing-session source change."""

        return cls(
            command_name=command_name,
            status="applied" if source_change.source_changed else "noop",
            source_change=source_change,
            cursor_state=source_change.cursor_state,
            undo_availability_change=source_change.undo_availability_change,
            reason=None if source_change.source_changed else noop_reason,
        )

    @classmethod
    def completed(
        cls,
        command_name: str,
        *,
        cursor_state: PromptCursorState | None = None,
        reason: str | None = None,
    ) -> "PromptCommandResult[TPayload]":
        """Build a result for a non-source command that completed successfully."""

        return cls(
            command_name=command_name,
            status="completed",
            cursor_state=cursor_state,
            reason=reason,
        )

    @classmethod
    def noop(
        cls,
        command_name: str,
        *,
        cursor_state: PromptCursorState | None = None,
        reason: str | None = None,
    ) -> "PromptCommandResult[TPayload]":
        """Build a result for a command that intentionally made no source change."""

        return cls(
            command_name=command_name,
            status="noop",
            cursor_state=cursor_state,
            reason=reason,
        )

    @classmethod
    def rejected(
        cls,
        command_name: str,
        *,
        reason: str,
    ) -> "PromptCommandResult[TPayload]":
        """Build a result for a command whose prepared input is no longer valid."""

        return cls(command_name=command_name, status="rejected", reason=reason)


class PromptEditorCommand(Protocol[TPayload]):
    """Execute one undo-safe prompt editor mutation through an editing session."""

    @property
    def name(self) -> str:
        """Return the stable command name used for diagnostics and tests."""

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Apply this command through the supplied editing session."""


class PromptCommandDispatcher(Generic[TPayload]):
    """Dispatch prompt editor commands against one editing-session owner."""

    def __init__(self, session: PromptEditingSession[TPayload]) -> None:
        """Store the editing session that remains source/cursor authority."""

        self._session = session

    @property
    def session(self) -> PromptEditingSession[TPayload]:
        """Return the editing session used by this dispatcher."""

        return self._session

    def execute(
        self,
        command: PromptEditorCommand[TPayload],
    ) -> PromptCommandResult[TPayload]:
        """Execute one command without adding widget or async ownership."""

        return command.execute(self._session)


from .autocomplete_commands import (  # noqa: E402
    PromptAcceptLoraAutocompleteCommand,
    PromptAcceptSceneAutocompleteCommand,
    PromptAcceptTagAutocompleteCommand,
    PromptAcceptWildcardAutocompleteCommand,
    PromptAutocompleteAcceptance,
    PromptLoraAutocompleteAcceptance,
    PromptSceneAutocompleteAcceptance,
    PromptTagAutocompleteAcceptance,
    PromptWildcardAutocompleteAcceptance,
    autocomplete_characters_match,
    autocomplete_completion_suffix,
    autocomplete_suffix_without_existing_right_text,
    build_autocomplete_acceptance_command,
)
from .clipboard_commands import (  # noqa: E402
    PromptClipboardCommandResult,
    PromptCopySelectionCommand,
    PromptCutSelectionCommand,
    PromptPasteTextCommand,
    PromptReplaceFullSourceCommand,
    PromptReplaceSourceRangeCommand,
    PromptSelectAllCommand,
    normalized_clipboard_paste_text,
)
from .diagnostic_commands import (  # noqa: E402
    PromptAddSpellingDiagnosticToDictionaryCommand,
    PromptDiagnosticAction,
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
from .paste_import_commands import (  # noqa: E402
    PromptApplyPreparedDanbooruImportCommand,
    PromptPasteImportCommandResult,
    PromptPreparedDanbooruImportRequest,
    build_prepared_danbooru_import_command,
)
from .feature_commands import (  # noqa: E402
    PromptFeatureCommandRequest,
    PromptFeatureSnapshotIdentity,
)
from .reorder_commands import (  # noqa: E402
    PromptCommitReorderLayoutCommand,
    PromptReorderCommandResult,
    PromptReorderLayoutCommitRequest,
    build_reorder_layout_commit_command,
)
from .trigger_word_commands import (  # noqa: E402
    PromptInsertTriggerWordsCommand,
    PromptTriggerWordInsertionRequest,
    build_trigger_word_insertion_command,
    prepare_trigger_word_insertion,
)
from .weight_commands import (  # noqa: E402
    PromptApplySyntaxWeightCommand,
    PromptSyntaxWeightAction,
    PromptWeightActionRequest,
    PromptWeightCommandResult,
    PromptWeightCursorPolicy,
    build_weight_action_command,
)

__all__ = [
    "PromptAcceptLoraAutocompleteCommand",
    "PromptAcceptSceneAutocompleteCommand",
    "PromptAcceptTagAutocompleteCommand",
    "PromptAcceptWildcardAutocompleteCommand",
    "PromptAddSpellingDiagnosticToDictionaryCommand",
    "PromptApplyPreparedDanbooruImportCommand",
    "PromptApplySyntaxWeightCommand",
    "PromptAutocompleteAcceptance",
    "PromptClipboardCommandResult",
    "PromptCommandDispatcher",
    "PromptCommandResult",
    "PromptCommandSourceIdentity",
    "PromptCommandSourceRange",
    "PromptCommandStatus",
    "PromptCommandTextReplacement",
    "PromptCommitReorderLayoutCommand",
    "PromptCopySelectionCommand",
    "PromptCutSelectionCommand",
    "PromptDiagnosticAction",
    "PromptDiagnosticCommandResult",
    "PromptDuplicateEmphasisDiagnosticAction",
    "PromptDuplicateIgnoreDiagnosticAction",
    "PromptDuplicateRemovalDiagnosticAction",
    "PromptEmphasizeFirstDuplicateDiagnosticCommand",
    "PromptEditorCommand",
    "PromptFeatureCommandRequest",
    "PromptFeatureSnapshotIdentity",
    "PromptIgnoreDuplicateDiagnosticCommand",
    "PromptIgnoreSpellingDiagnosticCommand",
    "PromptInsertTriggerWordsCommand",
    "PromptLoraAutocompleteAcceptance",
    "PromptPasteImportCommandResult",
    "PromptPasteTextCommand",
    "PromptPreparedDanbooruImportRequest",
    "PromptReorderCommandResult",
    "PromptReorderLayoutCommitRequest",
    "PromptRemoveDuplicateDiagnosticCommand",
    "PromptReplaceFullSourceCommand",
    "PromptReplaceSourceRangeCommand",
    "PromptReplaceSpellingDiagnosticCommand",
    "PromptSceneAutocompleteAcceptance",
    "PromptSelectAllCommand",
    "PromptSpellingDictionaryAddDiagnosticAction",
    "PromptSpellingIgnoreDiagnosticAction",
    "PromptSpellingReplacementDiagnosticAction",
    "PromptTagAutocompleteAcceptance",
    "PromptTriggerWordInsertionRequest",
    "PromptSyntaxWeightAction",
    "PromptWeightActionRequest",
    "PromptWeightCommandResult",
    "PromptWeightCursorPolicy",
    "PromptWildcardAutocompleteAcceptance",
    "autocomplete_characters_match",
    "autocomplete_completion_suffix",
    "autocomplete_suffix_without_existing_right_text",
    "build_autocomplete_acceptance_command",
    "build_diagnostic_action_command",
    "build_prepared_danbooru_import_command",
    "build_reorder_layout_commit_command",
    "build_trigger_word_insertion_command",
    "build_weight_action_command",
    "normalized_clipboard_paste_text",
    "prepare_trigger_word_insertion",
]
