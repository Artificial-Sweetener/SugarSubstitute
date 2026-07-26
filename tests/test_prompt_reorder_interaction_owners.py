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

"""Cover extracted prompt reorder interaction session and sync owners."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

import pytest
from PySide6.QtCore import QTimer

from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderRowView,
    PromptReorderStateView,
)
from substitute.application.prompt_editor.reorder.commit import (
    PromptReorderLayoutCommitRequest,
)
from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.reorder.lifecycle import (
    PromptReorderEntryRequest,
    PromptReorderLifecycleOwner,
)
from substitute.application.prompt_editor.reorder.preview_sync import (
    PromptReorderPreviewSyncContext,
)
from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCloseTransition,
    PromptReorderCommitOutcome,
    PromptReorderCommitSnapshot,
    PromptReorderSessionOwner,
    PromptReorderSessionState,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_cursor_selection import (
    PromptReorderCursor,
    PromptReorderCursorSelectionAdapter,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_commit_execution import (
    PromptReorderCommitExecutor,
)
from substitute.presentation.editor.prompt_editor.commands.reorder_commands import (
    PromptReorderCommandResult,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_preview_sync import (
    PromptReorderPreviewSyncController,
)


class _FakeSignal:
    """Store a single timer callback for deterministic scheduler tests."""

    def __init__(self) -> None:
        """Initialize with no connected callback."""

        self._callback: Callable[[], None] | None = None

    def connect(self, callback: Callable[[], None]) -> object:
        """Record the callback and return a connection sentinel."""

        self._callback = callback
        return object()

    def fire(self) -> None:
        """Invoke the connected callback when present."""

        if self._callback is not None:
            self._callback()


class _FakeQTimer:
    """Provide the small QTimer surface needed by preview sync tests."""

    instances: list["_FakeQTimer"] = []

    def __init__(self) -> None:
        """Initialize fake timer state."""

        self.timeout = _FakeSignal()
        self.started_intervals: list[int] = []
        self.stopped = 0
        self._active = False
        self.__class__.instances.append(self)

    def setSingleShot(self, single_shot: bool) -> None:  # noqa: N802
        """Accept single-shot configuration."""

        _ = single_shot

    def setInterval(self, interval: int) -> None:  # noqa: N802
        """Accept default interval configuration."""

        _ = interval

    def start(self, interval: int) -> None:
        """Mark this timer active with one explicit interval."""

        self.started_intervals.append(interval)
        self._active = True

    def stop(self) -> None:
        """Mark this timer inactive."""

        self.stopped += 1
        self._active = False

    def isActive(self) -> bool:  # noqa: N802
        """Return whether this timer is active."""

        return self._active

    def fire(self) -> None:
        """Run the scheduled timeout callback once."""

        self._active = False
        self.timeout.fire()


class _CursorSelectionDouble:
    """Provide the empty-selection query required by the cursor protocol."""

    def isEmpty(self) -> bool:  # noqa: N802
        """Return that this deterministic cursor has no selection."""

        return True


class _CursorDouble:
    """Record the Qt cursor boundary used by selection-restoration tests."""

    def __init__(self) -> None:
        """Initialize a cursor with no recorded position changes."""

        self.moves: list[tuple[int, object | None]] = []

    def position(self) -> int:
        """Return the deterministic current position."""

        return 0

    def selection(self) -> _CursorSelectionDouble:
        """Return the deterministic empty selection."""

        return _CursorSelectionDouble()

    def selectionStart(self) -> int:  # noqa: N802
        """Return the deterministic selection start."""

        return 0

    def selectionEnd(self) -> int:  # noqa: N802
        """Return the deterministic selection end."""

        return 0

    def setPosition(self, position: int, mode: object | None = None) -> None:  # noqa: N802
        """Record one cursor position update."""

        self.moves.append((position, mode))


class _CursorSurfaceDouble:
    """Expose a deterministic cursor surface for adapter owner tests."""

    def __init__(self) -> None:
        """Initialize one reusable cursor and publication counter."""

        self.cursor = _CursorDouble()
        self.published_cursors: list[object] = []

    def textCursor(self) -> PromptReorderCursor:  # noqa: N802
        """Return the current deterministic cursor."""

        return self.cursor

    def setTextCursor(self, cursor: PromptReorderCursor) -> None:  # noqa: N802
        """Record one cursor publication."""

        self.published_cursors.append(cursor)


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


def _sync_context() -> PromptReorderPreviewSyncContext:
    """Return a default deferred preview-sync context."""

    return PromptReorderPreviewSyncContext(
        gesture_id=10,
        event_id=20,
        pointer_active=False,
        dragged_segment_index=1,
        base_drag_layout_ready=True,
        requires_immediate_drag_geometry=False,
        requires_initial_landing_shadow=False,
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


def test_reorder_cursor_selection_adapter_restores_one_half_open_range() -> None:
    """The Qt adapter must publish both anchors exactly once for a close effect."""

    surface = _CursorSurfaceDouble()

    PromptReorderCursorSelectionAdapter().restore(
        surface,
        PromptReorderCloseTransition(selection_start=3, selection_end=8),
    )

    assert [position for position, _mode in surface.cursor.moves] == [3, 8]
    assert surface.published_cursors == [surface.cursor]


def test_reorder_cursor_selection_adapter_skips_absent_restore_effect() -> None:
    """A commit-relative selection must not cause redundant Qt cursor work."""

    surface = _CursorSurfaceDouble()

    PromptReorderCursorSelectionAdapter().restore(
        surface,
        PromptReorderCloseTransition(selection_start=None, selection_end=None),
    )

    assert surface.cursor.moves == []
    assert surface.published_cursors == []


def test_reorder_commit_executor_invokes_and_publishes_one_prepared_request() -> None:
    """Command execution owns one narrow call followed by one result publication."""

    class _Surface:
        def __init__(self) -> None:
            self.requests: list[object] = []

        def execute_reorder_action(
            self,
            request: PromptReorderLayoutCommitRequest,
            *,
            mutation_service: PromptMutationService,
            syntax_service: PromptSyntaxService,
            syntax_profile: PromptSyntaxProfile,
        ) -> PromptReorderCommandResult[object]:
            _ = mutation_service, syntax_service, syntax_profile
            self.requests.append(request)
            return PromptReorderCommandResult(command_name="reorder", status="applied")

        def toPlainText(self) -> str:  # noqa: N802
            return "alpha"

    class _ResultPort:
        def __init__(self) -> None:
            self.results: list[object] = []

        def apply_reorder_result(
            self, result: PromptReorderCommandResult[object]
        ) -> None:
            self.results.append(result)

    surface = _Surface()
    result_port = _ResultPort()
    request = PromptReorderLayoutCommitRequest(
        reorder_state=_state(0, 1), layout_view=_layout(0, 1), selected_chip_index=0
    )
    executor = PromptReorderCommitExecutor(
        surface,
        result_port=result_port,
        mutation_service=cast(PromptMutationService, object()),
        syntax_service=cast(PromptSyntaxService, object()),
        syntax_profile=cast(PromptSyntaxProfile, object()),
    )

    executor.execute(request, reason="owner_test")

    assert surface.requests == [request]
    assert len(result_port.results) == 1


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


def test_preview_sync_coalesces_repeated_requests() -> None:
    """Repeated preview requests should leave only the latest pending revision."""

    _FakeQTimer.instances.clear()
    sync_calls = 0
    decisions: list[bool] = []

    def run_sync() -> None:
        """Record approved expensive sync work."""

        nonlocal sync_calls
        sync_calls += 1

    owner = PromptReorderPreviewSyncController(
        interval_ms=16,
        run_sync=run_sync,
        timer_factory=cast(Callable[[], QTimer], _FakeQTimer),
    )

    owner.schedule(
        reason="preview_changed",
        context=_sync_context(),
        record_decision=decisions.append,
    )
    owner.schedule(
        reason="drag_move", context=_sync_context(), record_decision=decisions.append
    )
    owner.schedule(
        reason="drag_move", context=_sync_context(), record_decision=decisions.append
    )

    assert sync_calls == 0
    assert owner.state.pending_revision == 3
    assert owner.state.pending_reason == "drag_move"
    assert owner.state.scheduler_active is True
    assert decisions == [False, False, False]

    owner.flush_pending(reason="test")

    assert sync_calls == 1
    assert owner.state.pending_revision is None
    assert owner.state.last_applied_revision == 3


def test_scheduled_preview_sync_reports_elapsed_with_pending_context() -> None:
    """Timer-fired sync should keep the pending overlay context and elapsed hook."""

    _FakeQTimer.instances.clear()
    sync_calls = 0
    elapsed_samples: list[float] = []

    def run_sync() -> None:
        """Record approved expensive sync work."""

        nonlocal sync_calls
        sync_calls += 1

    owner = PromptReorderPreviewSyncController(
        interval_ms=16,
        run_sync=run_sync,
        timer_factory=cast(Callable[[], QTimer], _FakeQTimer),
    )

    owner.schedule(
        reason="drag_move",
        context=_sync_context(),
        record_decision=lambda _immediate: None,
        record_elapsed=elapsed_samples.append,
    )

    _FakeQTimer.instances[-1].fire()

    assert sync_calls == 1
    assert owner.state.pending_revision is None
    assert owner.state.last_applied_revision == 1
    assert len(elapsed_samples) == 1


def test_immediate_preview_sync_reports_elapsed_with_pending_context() -> None:
    """Immediate sync decisions should report elapsed time through the owner."""

    sync_calls = 0
    elapsed_samples: list[float] = []

    def run_sync() -> None:
        """Record approved immediate sync work."""

        nonlocal sync_calls
        sync_calls += 1

    context = PromptReorderPreviewSyncContext(
        gesture_id=10,
        event_id=20,
        pointer_active=False,
        dragged_segment_index=1,
        base_drag_layout_ready=True,
        requires_immediate_drag_geometry=True,
        requires_initial_landing_shadow=False,
    )
    owner = PromptReorderPreviewSyncController(
        interval_ms=16,
        run_sync=run_sync,
        timer_factory=cast(Callable[[], QTimer], _FakeQTimer),
    )

    owner.schedule(
        reason="drag_start",
        context=context,
        record_decision=lambda _immediate: None,
        record_elapsed=elapsed_samples.append,
    )

    assert sync_calls == 1
    assert owner.state.pending_revision is None
    assert owner.state.last_applied_revision == 1
    assert len(elapsed_samples) == 1


def test_stale_preview_sync_cannot_overwrite_commit_snapshot() -> None:
    """Stale preview sync rejection should not run code that can alter commit truth."""

    session_owner = PromptReorderSessionOwner()
    session_owner.start(
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
    session_owner.capture_snapshot(snapshot)

    def run_sync() -> None:
        """Fail if stale preview work reaches display sync."""

        session_owner.capture_snapshot(
            PromptReorderCommitSnapshot(
                reorder_state=_state(0, 1),
                layout_view=_layout(0, 1),
                ordered_chip_indices=(0, 1),
                active_segment_index=0,
                dragged_segment_index=None,
                has_reordered=False,
            )
        )

    owner = PromptReorderPreviewSyncController(
        interval_ms=16,
        run_sync=run_sync,
        timer_factory=cast(Callable[[], QTimer], _FakeQTimer),
    )
    owner.replace_state(
        pending_revision=3,
        pending_reason="drag_move",
        last_applied_revision=4,
    )

    owner.flush_pending(reason="test")

    assert session_owner.latest_commit_snapshot is snapshot
    assert session_owner.state.current_ordered_indices == (1, 0)
    assert owner.state.pending_revision is None
    assert owner.state.last_applied_revision == 4
