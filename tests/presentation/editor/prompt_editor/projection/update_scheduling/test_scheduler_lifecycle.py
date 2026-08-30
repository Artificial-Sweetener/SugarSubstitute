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

"""Verify pending-update timer lifecycle and teardown safety."""

from __future__ import annotations


from shiboken6 import delete

from substitute.presentation.editor.prompt_editor.projection.update_scheduler import (
    PendingProjectionUpdate,
    PromptProjectionUpdateScheduler,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.projection.update_scheduling.support import (
    _pending_update,
    _pending_update_at,
)


def test_projection_update_scheduler_applies_latest_update_only() -> None:
    """Scheduled projection updates should be latest-wins."""

    app = ensure_qapp()
    applied: list[PendingProjectionUpdate] = []
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=applied.append,
        interval_ms=0,
    )

    first = _pending_update("alpha", source_revision=1)
    second = _pending_update("alpha beta", source_revision=2)

    scheduler.schedule(first)
    scheduler.schedule(second)

    assert scheduler.has_pending_update() is True

    process_events(app)

    assert applied == [second]
    assert scheduler.has_pending_update() is False


def test_projection_update_scheduler_flush_now_is_idempotent() -> None:
    """Forced flushing should apply pending work once and then become a no-op."""

    ensure_qapp()
    applied: list[PendingProjectionUpdate] = []
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=applied.append,
        interval_ms=1000,
    )
    update = _pending_update("alpha", source_revision=1)

    scheduler.schedule(update)
    scheduler.flush_now(reason="cursor_rect")
    scheduler.flush_now(reason="cursor_rect")

    assert applied == [update]
    assert scheduler.has_pending_update() is False


def test_projection_update_scheduler_cancel_drops_pending_update() -> None:
    """Canceling should prevent a queued projection update from applying."""

    app = ensure_qapp()
    applied: list[PendingProjectionUpdate] = []
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=applied.append,
        interval_ms=0,
    )

    scheduler.schedule(_pending_update("alpha", source_revision=1))
    scheduler.cancel()
    process_events(app)

    assert applied == []
    assert scheduler.has_pending_update() is False


def test_projection_update_scheduler_cancel_tolerates_deleted_qt_timer() -> None:
    """Canceling during Qt teardown should not call a deleted timer wrapper."""

    ensure_qapp()
    applied: list[PendingProjectionUpdate] = []
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=applied.append,
        interval_ms=1000,
    )

    scheduler.schedule(_pending_update("alpha", source_revision=1))
    delete(scheduler._timer)  # noqa: SLF001
    scheduler.cancel()

    assert applied == []
    assert scheduler.has_pending_update() is False


def test_projection_update_scheduler_schedule_drops_update_after_deleted_qt_timer() -> (
    None
):
    """Scheduling after Qt teardown should clear pending work without crashing."""

    ensure_qapp()
    applied: list[PendingProjectionUpdate] = []
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=applied.append,
        interval_ms=1000,
    )

    delete(scheduler._timer)  # noqa: SLF001
    scheduler.schedule(_pending_update_at("alpha", source_revision=1, queued_at=10.0))

    assert applied == []
    assert scheduler.has_pending_update() is False


def test_projection_update_scheduler_flush_now_drops_update_after_deleted_qt_timer() -> (
    None
):
    """Forced flushing during Qt teardown should not apply into deleted widgets."""

    ensure_qapp()
    applied: list[PendingProjectionUpdate] = []
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=applied.append,
        interval_ms=1000,
    )
    scheduler._pending_update = _pending_update_at(  # noqa: SLF001
        "alpha",
        source_revision=1,
        queued_at=10.0,
    )
    scheduler._pending_started_at = 10.0  # noqa: SLF001

    delete(scheduler._timer)  # noqa: SLF001
    scheduler.flush_now(reason="test")

    assert applied == []
    assert scheduler.has_pending_update() is False
