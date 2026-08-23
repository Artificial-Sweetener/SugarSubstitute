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

"""Verify prompt reorder application session and lifecycle contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderRowView,
    PromptReorderStateView,
)
from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.reorder.lifecycle import (
    PromptReorderEntryRequest,
    PromptReorderLifecycleOwner,
)
from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCommitOutcome,
    PromptReorderCommitSnapshot,
    PromptReorderSessionOwner,
    PromptReorderSessionState,
)


def _layout(*indices: int) -> PromptReorderLayoutView:
    """Build one single-row reorder layout for owner tests."""

    return PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=indices),),
        gaps=(),
    )


def _state(*indices: int) -> PromptReorderStateView:
    """Build one same-row reorder state for owner tests."""

    return PromptReorderStateView(
        ordered_chip_indices=indices,
        separator_slots=tuple(", " for _ in indices[:-1]),
        has_trailing_comma=False,
    )


def test_reorder_session_captures_drag_snapshot_transition() -> None:
    """Drag-prepared snapshots should become authoritative commit state."""

    owner = PromptReorderSessionOwner()
    owner.start(
        layout_view=_layout(0, 1),
        reorder_state=_state(0, 1),
        ordered_indices=(0, 1),
        active_segment_index=1,
        selection_start=7,
        selection_end=7,
        selection_start_offset_within_active_chip=0,
        selection_end_offset_within_active_chip=0,
    )
    snapshot = PromptReorderCommitSnapshot(
        reorder_state=_state(1, 0),
        layout_view=_layout(1, 0),
        ordered_chip_indices=(1, 0),
        active_segment_index=1,
        dragged_segment_index=1,
        has_reordered=True,
    )

    owner.capture_snapshot(snapshot)

    assert owner.latest_commit_snapshot is snapshot
    assert owner.state.original_ordered_indices == (0, 1)
    assert owner.state.current_ordered_indices == (1, 0)
    assert owner.state.dragged_segment_index == 1
    assert owner.state.has_reordered is True


def test_reorder_lifecycle_starts_only_after_presentation_accepts_entry() -> None:
    """Entry planning cannot leave a live session when overlay entry is declined."""

    document_service = PromptDocumentService()
    owner = PromptReorderLifecycleOwner(document_service)
    plan = owner.prepare_entry(
        PromptReorderEntryRequest(
            document_view=document_service.build_document_view("alpha, beta"),
            cursor_position=7,
            selection_start=7,
            selection_end=7,
            selection_empty=True,
        )
    )

    assert plan is not None
    assert owner.session_state.is_active is False
    owner.start(plan)
    assert owner.session_state.is_active is True
    assert owner.session_state.active_segment_index == 1


def test_reorder_lifecycle_rejects_empty_entry_without_state_change() -> None:
    """Empty source planning cannot allocate a session or commit snapshot."""

    document_service = PromptDocumentService()
    owner = PromptReorderLifecycleOwner(document_service)

    plan = owner.prepare_entry(
        PromptReorderEntryRequest(
            document_view=document_service.build_document_view(""),
            cursor_position=0,
            selection_start=0,
            selection_end=0,
            selection_empty=True,
        )
    )

    assert plan is None
    assert owner.session_state.is_active is False
    assert owner.latest_commit_snapshot is None


def test_reorder_session_captures_keyboard_snapshot_transition() -> None:
    """Keyboard-prepared snapshots should update commit state without drag state."""

    owner = PromptReorderSessionOwner()
    owner.start(
        layout_view=_layout(0, 1, 2),
        reorder_state=_state(0, 1, 2),
        ordered_indices=(0, 1, 2),
        active_segment_index=1,
        selection_start=7,
        selection_end=7,
        selection_start_offset_within_active_chip=0,
        selection_end_offset_within_active_chip=0,
    )
    snapshot = PromptReorderCommitSnapshot(
        reorder_state=_state(1, 0, 2),
        layout_view=_layout(1, 0, 2),
        ordered_chip_indices=(1, 0, 2),
        active_segment_index=1,
        dragged_segment_index=None,
        has_reordered=True,
    )

    owner.capture_snapshot(snapshot)

    assert owner.latest_commit_snapshot is snapshot
    assert owner.state.current_ordered_indices == (1, 0, 2)
    assert owner.state.active_segment_index == 1
    assert owner.state.dragged_segment_index is None
    assert owner.state.has_reordered is True


def test_reorder_session_close_disables_commit_state() -> None:
    """Cancel and close should clear commit snapshot state."""

    owner = PromptReorderSessionOwner()
    owner.start(
        layout_view=_layout(0, 1),
        reorder_state=_state(0, 1),
        ordered_indices=(0, 1),
        active_segment_index=1,
        selection_start=7,
        selection_end=7,
        selection_start_offset_within_active_chip=0,
        selection_end_offset_within_active_chip=0,
    )

    transition = owner.close(restore_selection=False)

    assert transition.selection_start is None
    assert transition.selection_end is None
    assert owner.latest_commit_snapshot is None
    assert owner.state.is_active is False
    assert owner.state.current_ordered_indices == ()
    assert owner.state.has_reordered is False


def test_reorder_session_state_is_an_immutable_application_snapshot() -> None:
    """Presentation consumers must not mutate application session truth."""

    state = PromptReorderSessionState(is_active=True, active_segment_index=2)

    with pytest.raises(FrozenInstanceError):
        state.active_segment_index = 3  # type: ignore[misc]


def test_reorder_session_owner_prepares_complete_relative_selection_commit() -> None:
    """Commit policy should preserve relative selection after closing the overlay."""

    owner = PromptReorderSessionOwner()
    owner.start(
        layout_view=_layout(0, 1),
        reorder_state=_state(0, 1),
        ordered_indices=(0, 1),
        active_segment_index=1,
        selection_start=7,
        selection_end=8,
        selection_start_offset_within_active_chip=1,
        selection_end_offset_within_active_chip=2,
    )
    snapshot = PromptReorderCommitSnapshot(
        reorder_state=_state(1, 0),
        layout_view=_layout(1, 0),
        ordered_chip_indices=(1, 0),
        active_segment_index=1,
        dragged_segment_index=1,
        has_reordered=True,
    )

    plan = owner.finish_commit(
        snapshot,
        source_revision=4,
        source_length=11,
    )

    assert plan.outcome is PromptReorderCommitOutcome.COMMIT
    assert plan.request is not None
    assert plan.request.selected_chip_index == 1
    assert plan.request.selection_start_offset_within_selected_chip == 1
    assert plan.request.selection_end_offset_within_selected_chip == 2
    assert plan.request.source_revision == 4
    assert plan.request.source_length == 11
    assert plan.close_transition.selection_start is None
    assert plan.close_transition.selection_end is None
    assert owner.latest_commit_snapshot is None
    assert owner.state.is_active is False


@pytest.mark.parametrize(
    ("has_reordered", "has_state", "expected"),
    (
        (False, True, PromptReorderCommitOutcome.UNCHANGED),
        (True, False, PromptReorderCommitOutcome.MISSING_STATE),
    ),
)
def test_reorder_session_owner_rejects_noncommittable_snapshots(
    has_reordered: bool,
    has_state: bool,
    expected: PromptReorderCommitOutcome,
) -> None:
    """Application policy should classify no-op and incomplete snapshots."""

    owner = PromptReorderSessionOwner()
    owner.replace_state(
        PromptReorderSessionState(
            is_active=True,
            selection_start=3,
            selection_end=5,
        )
    )
    snapshot = PromptReorderCommitSnapshot(
        reorder_state=_state(0, 1) if has_state else None,
        layout_view=_layout(0, 1),
        ordered_chip_indices=(0, 1),
        active_segment_index=0,
        dragged_segment_index=None,
        has_reordered=has_reordered,
    )

    plan = owner.finish_commit(
        snapshot,
        source_revision=4,
        source_length=11,
    )

    assert plan.outcome is expected
    assert plan.request is None
    assert plan.close_transition.selection_start == 3
    assert plan.close_transition.selection_end == 5
    assert owner.latest_commit_snapshot is None
    assert owner.state.is_active is False
