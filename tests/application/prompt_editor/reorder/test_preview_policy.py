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

"""Verify Qt-free prompt-reorder preview freshness and publication policy."""

from __future__ import annotations

from substitute.application.prompt_editor.reorder.preview_schedule import (
    PromptReorderPreviewRequestDecision,
    PromptReorderPreviewSchedulePolicy,
    PromptReorderPreviewTimerDecision,
)
from substitute.application.prompt_editor.reorder.preview_sync import (
    PromptReorderPreviewFlushDecision,
    PromptReorderPreviewScheduleMode,
    PromptReorderPreviewSyncContext,
    PromptReorderPreviewSyncPolicy,
)


def test_schedule_policy_replaces_older_revision_latest_wins() -> None:
    """A newer request should replace older timer work in constant state."""

    policy = PromptReorderPreviewSchedulePolicy(pointer_defer_cap_ms=96.0)

    first = policy.request(
        revision=1,
        pointer_active=True,
        pointer_revision=10,
        timer_active=False,
        now=1.0,
    )
    second = policy.request(
        revision=2,
        pointer_active=True,
        pointer_revision=11,
        timer_active=True,
        now=1.001,
    )

    assert first is PromptReorderPreviewRequestDecision.POINTER_DEFERRED
    assert (
        second is PromptReorderPreviewRequestDecision.COALESCED_STALE_POINTER_DEFERRED
    )
    assert policy.replaced_revision == 1
    assert policy.scheduled_revision == 2
    assert policy.latest_requested_revision == 2


def test_schedule_policy_defers_pointer_motion_until_starvation_cap() -> None:
    """Pointer work should defer a wake-up only within the bounded cap."""

    policy = PromptReorderPreviewSchedulePolicy(pointer_defer_cap_ms=96.0)
    policy.request(
        revision=1,
        pointer_active=True,
        pointer_revision=10,
        timer_active=False,
        now=1.0,
    )

    assert policy.timer_decision(pointer_revision=11, now=1.050) is (
        PromptReorderPreviewTimerDecision.RESCHEDULE_POINTER
    )
    assert policy.timer_decision(pointer_revision=12, now=1.097) is (
        PromptReorderPreviewTimerDecision.RUN_AFTER_STARVATION
    )


def test_schedule_policy_clears_all_pending_truth() -> None:
    """Cancellation should leave no revision eligible for a later timer."""

    policy = PromptReorderPreviewSchedulePolicy(pointer_defer_cap_ms=96.0)
    policy.request(
        revision=4,
        pointer_active=False,
        pointer_revision=None,
        timer_active=False,
        now=1.0,
    )

    policy.clear()

    assert policy.scheduled_revision is None
    assert policy.latest_requested_revision is None
    assert policy.timer_decision(pointer_revision=None, now=2.0) is (
        PromptReorderPreviewTimerDecision.NO_PENDING
    )


def test_sync_policy_owns_immediate_and_deferred_publication_modes() -> None:
    """Geometry readiness should select sync mode without a Qt dependency."""

    policy = PromptReorderPreviewSyncPolicy()

    deferred = policy.request(
        reason="drag_move",
        context=_context(requires_immediate=False),
    )
    immediate = policy.request(
        reason="drag_start",
        context=_context(requires_immediate=True),
    )

    assert deferred is PromptReorderPreviewScheduleMode.DEFERRED
    assert immediate is PromptReorderPreviewScheduleMode.IMMEDIATE
    assert policy.pending_revision == 2


def test_sync_policy_rejects_revision_not_newer_than_publication() -> None:
    """A stale timer delivery must not regain publication authority."""

    policy = PromptReorderPreviewSyncPolicy()
    policy.replace_state(
        pending_revision=3,
        pending_reason="drag_move",
        last_applied_revision=4,
    )

    decision = policy.begin_flush()

    assert decision is PromptReorderPreviewFlushDecision.STALE
    assert policy.flush_revision == 3
    assert policy.last_applied_revision == 4
    assert policy.snapshot(scheduler_active=False).pending_revision is None


def test_sync_policy_advances_revision_only_after_successful_publication() -> None:
    """Failed preview construction must leave the last published revision intact."""

    policy = PromptReorderPreviewSyncPolicy()
    policy.request(reason="drag_move", context=_context(requires_immediate=False))
    assert policy.begin_flush() is PromptReorderPreviewFlushDecision.RUN

    policy.complete_flush(published=False)

    assert policy.last_applied_revision == 0
    assert policy.active_reason is None

    policy.request(reason="drag_move", context=_context(requires_immediate=False))
    assert policy.begin_flush() is PromptReorderPreviewFlushDecision.RUN
    policy.complete_flush(published=True)

    assert policy.last_applied_revision == 2
    assert policy.active_reason is None


def _context(*, requires_immediate: bool) -> PromptReorderPreviewSyncContext:
    """Build one deterministic application preview-sync context."""

    return PromptReorderPreviewSyncContext(
        gesture_id=10,
        event_id=20,
        pointer_active=True,
        dragged_segment_index=1,
        base_drag_layout_ready=not requires_immediate,
        requires_immediate_drag_geometry=requires_immediate,
        requires_initial_landing_shadow=False,
    )
