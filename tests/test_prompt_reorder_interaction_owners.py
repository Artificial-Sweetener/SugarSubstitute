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

from substitute.application.prompt_editor import (
    PromptReorderLayoutView,
    PromptReorderRowView,
    PromptReorderStateView,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_preview_sync import (
    PromptReorderPreviewSyncContext,
    PromptReorderPreviewSyncController,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_session import (
    PromptReorderSessionController,
)
from substitute.presentation.editor.prompt_editor.models import (
    PromptReorderCommitSnapshot,
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

    owner = PromptReorderSessionController()
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
    assert owner.session.original_ordered_indices == (0, 1)
    assert owner.session.current_ordered_indices == (1, 0)
    assert owner.session.dragged_segment_index == 1
    assert owner.session.has_reordered is True


def test_reorder_session_captures_keyboard_snapshot_transition() -> None:
    """Keyboard-prepared snapshots should update commit state without drag state."""

    owner = PromptReorderSessionController()
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
    assert owner.session.current_ordered_indices == (1, 0, 2)
    assert owner.session.active_segment_index == 1
    assert owner.session.dragged_segment_index is None
    assert owner.session.has_reordered is True


def test_reorder_session_reset_disables_commit_state() -> None:
    """Cancel and close should clear commit snapshot state."""

    owner = PromptReorderSessionController()
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

    owner.reset()

    assert owner.latest_commit_snapshot is None
    assert owner.session.is_active is False
    assert owner.session.current_ordered_indices == ()
    assert owner.session.has_reordered is False


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
        timer_factory=_FakeQTimer,
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
        timer_factory=_FakeQTimer,
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
        timer_factory=_FakeQTimer,
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

    session_owner = PromptReorderSessionController()
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
        timer_factory=_FakeQTimer,
    )
    owner.replace_state(
        pending_revision=3,
        pending_reason="drag_move",
        last_applied_revision=4,
    )

    owner.flush_pending(reason="test")

    assert session_owner.latest_commit_snapshot is snapshot
    assert session_owner.session.current_ordered_indices == (1, 0)
    assert owner.state.pending_revision is None
    assert owner.state.last_applied_revision == 4
