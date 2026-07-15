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

"""Define source-backed reorder commands for prompt editing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from substitute.application.prompt_editor import (
    PromptMutation,
    PromptMutationService,
    PromptReorderLayoutView,
    PromptReorderStateView,
    PromptSyntaxProfile,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptEditingSession,
    PromptSourceNormalizer,
    PromptUndoSnapshot,
)
from substitute.shared.logging.logger import get_logger, log_warning_exception

from . import PromptCommandResult, PromptCommandSourceIdentity

TPayload = TypeVar("TPayload")

_LOGGER = get_logger("presentation.editor.prompt_editor.commands.reorder_commands")


@dataclass(frozen=True, slots=True)
class PromptReorderLayoutCommitRequest:
    """Describe one prepared prompt reorder layout commit."""

    selected_chip_index: int | None
    reorder_state: PromptReorderStateView
    layout_view: PromptReorderLayoutView | None = None
    source_identity: PromptCommandSourceIdentity | None = None
    selection_start_offset_within_selected_chip: int | None = None
    selection_end_offset_within_selected_chip: int | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderCommandResult(PromptCommandResult[TPayload]):
    """Report a reorder command mutation and optional prepared render plan."""

    mutation: PromptMutation | None = None
    render_plan: PromptSyntaxRenderPlan | None = None


@dataclass(frozen=True, slots=True)
class PromptCommitReorderLayoutCommand(Generic[TPayload]):
    """Commit one prepared reorder layout through the editing session."""

    request: PromptReorderLayoutCommitRequest
    mutation_service: PromptMutationService
    syntax_service: PromptSyntaxService
    syntax_profile: PromptSyntaxProfile
    normalizer: PromptSourceNormalizer
    exact_source: bool
    record_undo: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]
    name: str = "commit_reorder_layout"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptReorderCommandResult[TPayload]:
        """Apply this reorder commit through the supplied session."""

        stale_result = _stale_result(
            command_name=self.name,
            session=session,
            source_identity=self.request.source_identity,
        )
        if stale_result is not None:
            return stale_result

        mutation = self.mutation_service.reorder_state(
            session.source_text,
            reorder_state=self.request.reorder_state,
            selected_chip_index=self.request.selected_chip_index,
        )
        adjusted_mutation = _mutation_with_command_selection(
            mutation,
            request=self.request,
        )
        render_plan = _render_plan_for_mutation(
            syntax_service=self.syntax_service,
            syntax_profile=self.syntax_profile,
            mutation=adjusted_mutation,
        )
        cursor_position, anchor_position = _cursor_output_for_mutation(
            session=session,
            mutation=adjusted_mutation,
        )
        source_change = session.replace_full_source(
            adjusted_mutation.text,
            cursor_position=cursor_position,
            anchor_position=anchor_position,
            normalizer=self.normalizer,
            exact_source=self.exact_source,
            record_undo=self.record_undo,
            clear_history=False,
            undo_snapshot=self.undo_snapshot,
        )
        return PromptReorderCommandResult(
            command_name=self.name,
            status="applied" if source_change.source_changed else "noop",
            source_change=source_change,
            cursor_state=source_change.cursor_state,
            undo_availability_change=source_change.undo_availability_change,
            reason=None if source_change.source_changed else "same_source",
            mutation=adjusted_mutation,
            render_plan=render_plan,
        )


def build_reorder_layout_commit_command(
    request: PromptReorderLayoutCommitRequest,
    *,
    mutation_service: PromptMutationService,
    syntax_service: PromptSyntaxService,
    syntax_profile: PromptSyntaxProfile,
    normalizer: PromptSourceNormalizer,
    exact_source: bool,
    record_undo: bool,
    undo_snapshot: PromptUndoSnapshot[TPayload],
) -> PromptCommitReorderLayoutCommand[TPayload]:
    """Return the executable command for one prepared reorder layout commit."""

    return PromptCommitReorderLayoutCommand(
        request=request,
        mutation_service=mutation_service,
        syntax_service=syntax_service,
        syntax_profile=syntax_profile,
        normalizer=normalizer,
        exact_source=exact_source,
        record_undo=record_undo,
        undo_snapshot=undo_snapshot,
    )


def _mutation_with_command_selection(
    mutation: PromptMutation,
    *,
    request: PromptReorderLayoutCommitRequest,
) -> PromptMutation:
    """Return mutation selection according to the prepared reorder commit policy."""

    start_offset = request.selection_start_offset_within_selected_chip
    end_offset = request.selection_end_offset_within_selected_chip
    if (
        mutation.selection_start is None
        or mutation.selection_end is None
        or start_offset is None
        or end_offset is None
    ):
        return PromptMutation(
            text=mutation.text,
            selection_start=None,
            selection_end=None,
            document_view=mutation.document_view,
        )

    chip_length = max(0, mutation.selection_end - mutation.selection_start)
    relative_selection_start = mutation.selection_start + max(
        0,
        min(start_offset, chip_length),
    )
    relative_selection_end = mutation.selection_start + max(
        0,
        min(end_offset, chip_length),
    )
    return PromptMutation(
        text=mutation.text,
        selection_start=min(relative_selection_start, relative_selection_end),
        selection_end=max(relative_selection_start, relative_selection_end),
        document_view=mutation.document_view,
    )


def _cursor_output_for_mutation(
    *,
    session: PromptEditingSession[TPayload],
    mutation: PromptMutation,
) -> tuple[int, int]:
    """Return the command cursor output for one reorder mutation."""

    source_length = len(mutation.text)
    if mutation.selection_start is not None and mutation.selection_end is not None:
        return (
            max(0, min(mutation.selection_end, source_length)),
            max(0, min(mutation.selection_start, source_length)),
        )
    return (
        max(0, min(session.cursor_position, source_length)),
        max(0, min(session.anchor_position, source_length)),
    )


def _render_plan_for_mutation(
    *,
    syntax_service: PromptSyntaxService,
    syntax_profile: PromptSyntaxProfile,
    mutation: PromptMutation,
) -> PromptSyntaxRenderPlan | None:
    """Build a render plan for immediate prompt-state adoption when possible."""

    try:
        return syntax_service.build_render_plan(
            mutation.document_view,
            syntax_profile,
        )
    except Exception as error:
        log_warning_exception(
            _LOGGER,
            "Prompt reorder render-plan refresh failed",
            error=error,
            source_length=len(mutation.document_view.source_text),
        )
        return None


def _stale_result(
    *,
    command_name: str,
    session: PromptEditingSession[TPayload],
    source_identity: PromptCommandSourceIdentity | None,
) -> PromptReorderCommandResult[TPayload] | None:
    """Return a stale rejection for a mismatched prepared source identity."""

    if source_identity is None:
        return None
    if source_identity.matches(
        source_revision=session.source_revision,
        source_length=len(session.source_text),
    ):
        return None
    return PromptReorderCommandResult(
        command_name=command_name,
        status="rejected",
        reason="stale_source",
    )


__all__ = [
    "PromptCommitReorderLayoutCommand",
    "PromptReorderCommandResult",
    "PromptReorderLayoutCommitRequest",
    "build_reorder_layout_commit_command",
]
