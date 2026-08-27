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

"""Verify adaptive projection batch age and supersession behavior."""

from __future__ import annotations

import logging
from typing import Any, cast

import pytest

from substitute.presentation.editor.prompt_editor.projection.update_scheduler import (
    PendingProjectionUpdate,
    PromptProjectionSchedulingPolicy,
    PromptProjectionUpdateScheduler,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.projection.update_scheduling.support import (
    _ManualClock,
    _RestartRecordingTimer,
    _pending_update,
    _pending_update_at,
)


def test_projection_update_scheduler_preserves_oldest_pending_age_on_supersede() -> (
    None
):
    """Superseded projection batches should age from the first queued update."""

    ensure_qapp()
    clock = _ManualClock(10.0)
    applied: list[PendingProjectionUpdate] = []
    policy = PromptProjectionSchedulingPolicy(
        active_typing_delay_ms=1000,
        max_stale_ms=75,
    )
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=applied.append,
        scheduling_policy=policy,
        prompt_activity_elapsed_ms=lambda: 0.0,
        output_activity_elapsed_ms=lambda: None,
        now=clock,
    )

    scheduler.schedule(
        _pending_update_at("alpha", source_revision=1, queued_at=clock())
    )
    clock.advance(0.08)
    scheduler.schedule(
        _pending_update_at("alpha beta", source_revision=2, queued_at=clock())
    )

    assert applied == []
    assert scheduler.has_pending_update() is True
    assert scheduler._pending_superseded_count == 1  # noqa: SLF001
    assert scheduler._interval_ms == policy.idle_delay_ms  # noqa: SLF001


def test_projection_update_scheduler_flush_clears_age_and_supersedes() -> None:
    """Applying a pending projection should reset batch age bookkeeping."""

    ensure_qapp()
    applied: list[PendingProjectionUpdate] = []
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=applied.append,
        interval_ms=1000,
    )

    first = _pending_update("alpha", source_revision=1)
    second = _pending_update("alpha beta", source_revision=2)
    scheduler.schedule(first)
    scheduler.schedule(second)
    scheduler.flush_now(reason="test")

    assert applied == [second]
    assert scheduler._pending_started_at is None  # noqa: SLF001
    assert scheduler._pending_superseded_count == 0  # noqa: SLF001


def test_projection_update_scheduler_logs_schedule_and_flush_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Projection scheduler logs should expose delay and flush decisions."""

    ensure_qapp()
    applied: list[PendingProjectionUpdate] = []
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=applied.append,
        interval_ms=1000,
    )
    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.editor.prompt_editor.projection.update_scheduler",
    )

    scheduler.schedule(_pending_update("alpha", source_revision=1))
    scheduler.flush_now(reason="test")

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "prompt_projection_update.scheduled" in message
        and "delay_ms=1000" in message
        and "update_reason=test" in message
        for message in messages
    )
    assert any(
        "prompt_projection_update.flushed" in message
        and "flush_reason=test" in message
        and "update_reason=test" in message
        for message in messages
    )


def test_projection_update_scheduler_cancel_clears_age_and_supersedes() -> None:
    """Canceling a pending projection should reset batch age bookkeeping."""

    ensure_qapp()
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=lambda _update: None,
        interval_ms=1000,
    )

    scheduler.schedule(_pending_update("alpha", source_revision=1))
    scheduler.schedule(_pending_update("alpha beta", source_revision=2))
    scheduler.cancel()

    assert scheduler._pending_started_at is None  # noqa: SLF001
    assert scheduler._pending_superseded_count == 0  # noqa: SLF001


def test_projection_update_scheduler_cancels_only_unchanged_stale_safe_source() -> None:
    """Key handling may drop stale-safe metadata work but not unprojected text."""

    ensure_qapp()
    applied: list[PendingProjectionUpdate] = []
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=applied.append,
        interval_ms=1000,
    )

    scheduler.schedule(_pending_update_at("alpha x", source_revision=1, queued_at=1.0))

    assert scheduler.cancel_if_stale_safe_source_unchanged("alpha") is False
    assert scheduler.has_pending_update() is True

    assert scheduler.cancel_if_stale_safe_source_unchanged("alpha x") is True
    assert scheduler.has_pending_update() is False
    assert applied == []


def test_projection_update_scheduler_forces_max_stale_on_supersede() -> None:
    """Oldest pending age should force immediate scheduling when the cap is reached."""

    ensure_qapp()
    applied: list[PendingProjectionUpdate] = []
    policy = PromptProjectionSchedulingPolicy(
        active_typing_delay_ms=1000,
        max_stale_ms=75,
    )
    clock = _ManualClock(10.0)
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=applied.append,
        scheduling_policy=policy,
        prompt_activity_elapsed_ms=lambda: 0.0,
        output_activity_elapsed_ms=lambda: None,
        now=clock,
    )

    scheduler.schedule(
        _pending_update_at("alpha", source_revision=1, queued_at=clock())
    )
    clock.advance(0.08)
    scheduler.schedule(
        _pending_update_at("alpha beta", source_revision=2, queued_at=clock())
    )

    assert scheduler._interval_ms == policy.idle_delay_ms  # noqa: SLF001


def test_projection_update_scheduler_extends_active_typing_timer_on_supersede() -> None:
    """Fresh safe-typing updates should push GUI-thread catch-up past the burst."""

    ensure_qapp()
    policy = PromptProjectionSchedulingPolicy(
        active_typing_delay_ms=180,
        max_stale_ms=750,
    )
    clock = _ManualClock(10.0)
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=lambda _update: None,
        scheduling_policy=policy,
        prompt_activity_elapsed_ms=lambda: 0.0,
        output_activity_elapsed_ms=lambda: None,
        now=clock,
    )
    timer = _RestartRecordingTimer(remaining_ms=50)
    scheduler._timer = cast(Any, timer)  # noqa: SLF001

    scheduler.schedule(
        _pending_update_at("alpha", source_revision=1, queued_at=clock())
    )
    scheduler.schedule(
        _pending_update_at("alpha beta", source_revision=2, queued_at=clock())
    )

    assert timer.start_calls == [policy.active_typing_delay_ms] * 2
    assert timer.stop_calls == 1
    assert scheduler.has_pending_update() is True
