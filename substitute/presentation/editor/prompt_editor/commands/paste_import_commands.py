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

from dataclasses import dataclass
from typing import Generic, TypeVar

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

        source_change = session.replace_source_range(
            start=source_range.start,
            end=source_range.end,
            replacement_text=self.request.import_text,
            normalizer=self.normalizer,
            origin=PromptSourceEditOrigin.PASTE,
            exact_source=self.exact_source,
            record_undo=self.record_undo,
            undo_snapshot=self.undo_snapshot,
        )
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
) -> PromptApplyPreparedDanbooruImportCommand[TPayload]:
    """Return the executable command for one prepared Danbooru import insertion."""

    return PromptApplyPreparedDanbooruImportCommand(
        request=request,
        normalizer=normalizer,
        exact_source=exact_source,
        record_undo=record_undo,
        undo_snapshot=undo_snapshot,
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
