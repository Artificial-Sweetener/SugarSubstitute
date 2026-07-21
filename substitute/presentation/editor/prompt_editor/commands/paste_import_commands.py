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

"""Define prepared paste/import commands for prompt editing."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Generic, TypeVar

from substitute.application.prompt_editor.prompt_structured_text_mutation_service import (
    PromptStructuredTextMutationService,
)
from substitute.domain.prompt import SourceRange
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptEditingSession,
    PromptSourceEditOrigin,
    PromptSourceNormalizer,
    PromptUndoSnapshot,
)

from . import (
    PromptCommandResult,
    PromptCommandSourceIdentity,
    PromptCommandSourceRange,
)

TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class PromptPreparedDanbooruImportRequest(Generic[TPayload]):
    """Describe one prepared Danbooru import insertion."""

    source_range: PromptCommandSourceRange
    expected_pasted_text: str
    import_text: str
    pasted_undo_snapshot: PromptUndoSnapshot[TPayload]
    source_identity: PromptCommandSourceIdentity | None = None


@dataclass(frozen=True, slots=True)
class PromptPasteImportCommandResult(PromptCommandResult[TPayload]):
    """Report a prepared paste/import command result."""

    discarded_intermediate_undo_state: bool = False


@dataclass(frozen=True, slots=True)
class PromptApplyPreparedDanbooruImportCommand(Generic[TPayload]):
    """Apply prepared Danbooru import text through the editing session."""

    request: PromptPreparedDanbooruImportRequest[TPayload]
    normalizer: PromptSourceNormalizer
    exact_source: bool
    record_undo: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]
    structured_text_mutations: PromptStructuredTextMutationService | None = None
    name: str = "apply_prepared_danbooru_import"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptPasteImportCommandResult[TPayload]:
        """Replace the still-matching pasted URL slice with prepared import text."""

        stale_result = _stale_result(
            command_name=self.name,
            session=session,
            source_identity=self.request.source_identity,
        )
        if stale_result is not None:
            return stale_result

        source_range = self.request.source_range
        if not source_range.is_within(len(session.source_text)):
            return PromptPasteImportCommandResult(
                command_name=self.name,
                status="rejected",
                reason="range_out_of_bounds",
            )
        if (
            session.source_text[source_range.start : source_range.end]
            != self.request.expected_pasted_text
        ):
            return PromptPasteImportCommandResult(
                command_name=self.name,
                status="rejected",
                reason="pasted_text_changed",
            )

        replacement_start = source_range.start
        replacement_end = source_range.end
        replacement_text = self.request.import_text
        exact_source = self.exact_source
        cursor_position: int | None = None
        if self.structured_text_mutations is not None:
            structured_replacement = (
                self.structured_text_mutations.replacement_for_range(
                    session.source_text,
                    SourceRange(source_range.start, source_range.end),
                    self.request.import_text,
                )
            )
            if structured_replacement is None:
                return PromptPasteImportCommandResult(
                    command_name=self.name,
                    status="rejected",
                    reason="prompt_value_unavailable",
                )
            replacement_start = structured_replacement.source_range.start
            replacement_end = structured_replacement.source_range.end
            replacement_text = structured_replacement.replacement_text
            exact_source = structured_replacement.exact_source
            cursor_position = structured_replacement.cursor_position

        source_change = session.replace_source_range(
            start=replacement_start,
            end=replacement_end,
            replacement_text=replacement_text,
            normalizer=self.normalizer,
            origin=PromptSourceEditOrigin.PASTE,
            exact_source=exact_source,
            record_undo=self.record_undo,
            undo_snapshot=self.undo_snapshot,
        )
        if cursor_position is not None:
            cursor_state = session.set_cursor_positions(
                cursor_position=cursor_position,
                anchor_position=cursor_position,
            )
            source_change = replace(source_change, cursor_state=cursor_state)
        discard_availability_change = None
        if source_change.source_changed:
            discard_availability_change = session.discard_trailing_undo_state(
                self.request.pasted_undo_snapshot
            )
        return PromptPasteImportCommandResult(
            command_name=self.name,
            status="applied" if source_change.source_changed else "noop",
            source_change=source_change,
            cursor_state=source_change.cursor_state,
            undo_availability_change=(
                discard_availability_change
                if discard_availability_change is not None
                else source_change.undo_availability_change
            ),
            reason=None if source_change.source_changed else "same_source",
            discarded_intermediate_undo_state=discard_availability_change is not None,
        )


def build_prepared_danbooru_import_command(
    request: PromptPreparedDanbooruImportRequest[TPayload],
    *,
    normalizer: PromptSourceNormalizer,
    exact_source: bool,
    record_undo: bool,
    undo_snapshot: PromptUndoSnapshot[TPayload],
    structured_text_mutations: PromptStructuredTextMutationService | None = None,
) -> PromptApplyPreparedDanbooruImportCommand[TPayload]:
    """Return the executable command for one prepared Danbooru import insertion."""

    return PromptApplyPreparedDanbooruImportCommand(
        request=request,
        normalizer=normalizer,
        exact_source=exact_source,
        record_undo=record_undo,
        undo_snapshot=undo_snapshot,
        structured_text_mutations=structured_text_mutations,
    )


def _stale_result(
    *,
    command_name: str,
    session: PromptEditingSession[TPayload],
    source_identity: PromptCommandSourceIdentity | None,
) -> PromptPasteImportCommandResult[TPayload] | None:
    """Return a stale rejection for a mismatched prepared source identity."""

    if source_identity is None:
        return None
    if source_identity.matches(
        source_revision=session.source_revision,
        source_length=len(session.source_text),
    ):
        return None
    return PromptPasteImportCommandResult(
        command_name=command_name,
        status="rejected",
        reason="stale_source",
    )


__all__ = [
    "PromptApplyPreparedDanbooruImportCommand",
    "PromptPasteImportCommandResult",
    "PromptPreparedDanbooruImportRequest",
    "build_prepared_danbooru_import_command",
]
