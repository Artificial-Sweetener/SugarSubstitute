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

"""Tests for Phase 3.6 prompt editor reorder commands."""

from __future__ import annotations

from typing import cast

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptMutationService,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
    PromptReorderStateView,
    PromptSourceNormalizationService,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandDispatcher,
    PromptCommandSourceIdentity,
    PromptReorderCommandResult,
    PromptReorderLayoutCommitRequest,
    build_reorder_layout_commit_command,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)


def _session(
    source_text: str,
    *,
    cursor_position: int | None = None,
    anchor_position: int | None = None,
) -> PromptEditingSession[str]:
    """Return one editing session for reorder command tests."""

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


def _source_identity(session: PromptEditingSession[str]) -> PromptCommandSourceIdentity:
    """Return the current source identity for stale-command tests."""

    return PromptCommandSourceIdentity(
        source_revision=session.source_revision,
        source_length=len(session.source_text),
    )


def _state(
    ordered_chip_indices: tuple[int, ...],
    separator_slots: tuple[str, ...],
    *,
    has_trailing_comma: bool = False,
) -> PromptReorderStateView:
    """Return authoritative reorder state for command tests."""

    return PromptReorderStateView(
        ordered_chip_indices=ordered_chip_indices,
        separator_slots=separator_slots,
        has_trailing_comma=has_trailing_comma,
    )


def _execute_reorder_request(
    session: PromptEditingSession[str],
    request: PromptReorderLayoutCommitRequest,
) -> PromptReorderCommandResult[str]:
    """Execute one reorder command request through the real dispatcher."""

    command = build_reorder_layout_commit_command(
        request,
        mutation_service=PromptMutationService(),
        syntax_service=PromptSyntaxService(EmptyPromptWildcardCatalogGateway()),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard", "lora"),
        normalizer=PromptSourceNormalizationService(),
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    return cast(
        PromptReorderCommandResult[str],
        PromptCommandDispatcher(session).execute(command),
    )


def test_reorder_layout_command_commits_prepared_layout() -> None:
    """Reorder layout commands should mutate source through the session owner."""

    session = _session("alpha, beta", cursor_position=len("alpha, beta"))
    layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(1, 0)),),
        gaps=(),
    )

    result = _execute_reorder_request(
        session,
        PromptReorderLayoutCommitRequest(
            selected_chip_index=1,
            reorder_state=_state((1, 0), (", ",)),
            layout_view=layout_view,
            source_identity=_source_identity(session),
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "beta, alpha"
    assert result.mutation is not None
    assert result.mutation.selection_start is None
    assert result.mutation.selection_end is None
    assert result.render_plan is not None
    assert result.cursor_state == PromptCursorState(
        cursor_position=len("beta, alpha"),
        anchor_position=len("beta, alpha"),
    )
    assert session.can_undo()


def test_reorder_layout_command_restores_relative_chip_caret() -> None:
    """Reorder commands should restore stored chip-relative cursor offsets."""

    session = _session("alpha, beta", cursor_position=7)
    layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(1, 0)),),
        gaps=(),
    )

    result = _execute_reorder_request(
        session,
        PromptReorderLayoutCommitRequest(
            selected_chip_index=1,
            reorder_state=_state((1, 0), (", ",)),
            layout_view=layout_view,
            selection_start_offset_within_selected_chip=2,
            selection_end_offset_within_selected_chip=2,
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "beta, alpha"
    assert result.mutation is not None
    assert result.mutation.selection_start == 2
    assert result.mutation.selection_end == 2
    assert result.cursor_state == PromptCursorState(
        cursor_position=2,
        anchor_position=2,
    )


def test_reorder_layout_command_preserves_reversed_relative_selection() -> None:
    """Relative selections should clamp and sort inside the moved chip range."""

    session = _session("alpha, beta", cursor_position=11, anchor_position=7)
    layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(1, 0)),),
        gaps=(),
    )

    result = _execute_reorder_request(
        session,
        PromptReorderLayoutCommitRequest(
            selected_chip_index=1,
            reorder_state=_state((1, 0), (", ",)),
            layout_view=layout_view,
            selection_start_offset_within_selected_chip=4,
            selection_end_offset_within_selected_chip=1,
        ),
    )

    assert result.status == "applied"
    assert result.mutation is not None
    assert result.mutation.selection_start == 1
    assert result.mutation.selection_end == 4
    assert result.cursor_state == PromptCursorState(
        cursor_position=4,
        anchor_position=1,
    )


def test_reorder_layout_command_preserves_blank_line_gap_layout() -> None:
    """Reorder commands should preserve typed blank-line gap placement."""

    session = _session("alpha,\n\n\n\n\nbeta, gamma")
    layout_view = PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0,)),
            PromptReorderRowView(row_index=1, chip_indices=(2, 1)),
        ),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n\n",
                blank_line_count=1,
            ),
        ),
    )

    result = _execute_reorder_request(
        session,
        PromptReorderLayoutCommitRequest(
            selected_chip_index=2,
            reorder_state=_state((0, 2, 1), (",\n\n", ", ")),
            layout_view=layout_view,
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "alpha,\n\ngamma, beta"
    assert result.render_plan is not None


def test_reorder_layout_command_rejects_stale_source_identity() -> None:
    """Reorder commands should fail closed when prepared source identity changed."""

    session = _session("alpha, beta")
    layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(1, 0)),),
        gaps=(),
    )

    result = _execute_reorder_request(
        session,
        PromptReorderLayoutCommitRequest(
            selected_chip_index=1,
            reorder_state=_state((1, 0), (", ",)),
            layout_view=layout_view,
            source_identity=PromptCommandSourceIdentity(
                source_revision=session.source_revision + 1,
                source_length=len(session.source_text),
            ),
        ),
    )

    assert result.status == "rejected"
    assert result.reason == "stale_source"
    assert session.source_text == "alpha, beta"
    assert not session.can_undo()


def test_reorder_layout_command_reports_noop_for_same_layout() -> None:
    """Same-layout commits should still expose mutation state without source churn."""

    source_text = "alpha, beta"
    session = _session(source_text, cursor_position=3, anchor_position=3)
    layout_view = (
        PromptDocumentService()
        .build_reorder_session_view(
            PromptDocumentService().build_document_view(source_text)
        )
        .layout_view
    )
    reorder_state = (
        PromptDocumentService()
        .build_reorder_session_view(
            PromptDocumentService().build_document_view(source_text)
        )
        .reorder_state
    )

    result = _execute_reorder_request(
        session,
        PromptReorderLayoutCommitRequest(
            selected_chip_index=0,
            reorder_state=reorder_state,
            layout_view=layout_view,
        ),
    )

    assert result.status == "noop"
    assert result.reason == "same_source"
    assert session.source_text == source_text
    assert result.mutation is not None
    assert result.mutation.selection_start is None
    assert result.mutation.selection_end is None
    assert result.cursor_state == PromptCursorState(
        cursor_position=3,
        anchor_position=3,
    )


def test_reorder_layout_command_commits_authoritative_separator_state() -> None:
    """Reorder commits should not invent spaces from layout reconstruction."""

    session = _session("alpha,beta,gamma")
    layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(1, 0, 2)),),
        gaps=(),
    )

    result = _execute_reorder_request(
        session,
        PromptReorderLayoutCommitRequest(
            selected_chip_index=1,
            reorder_state=_state((1, 0, 2), (",", ",")),
            layout_view=layout_view,
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "beta,alpha,gamma"
