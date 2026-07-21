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

"""Tests for prompt projection update scheduling."""

from __future__ import annotations

import os
import logging
from time import perf_counter
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QFontMetricsF, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import delete

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.editor.prompt_editor.projection.update_scheduler import (
    PendingProjectionUpdate,
    PromptProjectionScheduleContext,
    PromptProjectionSchedulingPolicy,
    PromptProjectionUpdateScheduler,
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.prompt_projection_surface_test_helpers import (
    delay_projection_update_scheduler,
    first_emphasis_token,
    flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    valid_transient_insertion_overlay,
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
    scheduler.schedule(
        _pending_update_at("alpha", source_revision=1, queued_at=perf_counter())
    )

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
        queued_at=perf_counter(),
    )
    scheduler._pending_started_at = perf_counter()  # noqa: SLF001

    delete(scheduler._timer)  # noqa: SLF001
    scheduler.flush_now(reason="test")

    assert applied == []
    assert scheduler.has_pending_update() is False


def test_projection_scheduling_policy_delays_recent_prompt_activity() -> None:
    """Safe typing should land after one active typing frame by default."""

    policy = PromptProjectionSchedulingPolicy()

    decision = policy.choose_delay(
        PromptProjectionScheduleContext(
            reason="safe_typing",
            pending_age_ms=0.0,
            prompt_activity_elapsed_ms=5.0,
            output_activity_elapsed_ms=None,
            pending_superseded_count=0,
            stale_safe=True,
        )
    )

    assert decision.delay_ms == policy.active_typing_delay_ms
    assert decision.prompt_activity_recent is True
    assert decision.output_activity_recent is False
    assert decision.force_due_to_max_stale is False


def test_projection_scheduling_policy_uses_output_busy_delay() -> None:
    """Recent output activity should give safe typing projection a wider slot."""

    policy = PromptProjectionSchedulingPolicy()

    decision = policy.choose_delay(
        PromptProjectionScheduleContext(
            reason="safe_typing",
            pending_age_ms=0.0,
            prompt_activity_elapsed_ms=5.0,
            output_activity_elapsed_ms=20.0,
            pending_superseded_count=0,
            stale_safe=True,
        )
    )

    assert decision.delay_ms == policy.output_busy_delay_ms
    assert decision.prompt_activity_recent is True
    assert decision.output_activity_recent is True


def test_projection_scheduling_policy_uses_idle_delay_without_activity() -> None:
    """Idle safe projection work should land on the normal next turn."""

    policy = PromptProjectionSchedulingPolicy()

    decision = policy.choose_delay(
        PromptProjectionScheduleContext(
            reason="prompt_state",
            pending_age_ms=0.0,
            prompt_activity_elapsed_ms=None,
            output_activity_elapsed_ms=None,
            pending_superseded_count=0,
            stale_safe=True,
        )
    )

    assert decision.delay_ms == policy.idle_delay_ms
    assert decision.reason == "idle"


def test_projection_scheduling_policy_enforces_max_stale_cap() -> None:
    """Old pending safe projection work should land immediately."""

    policy = PromptProjectionSchedulingPolicy(max_stale_ms=75)

    decision = policy.choose_delay(
        PromptProjectionScheduleContext(
            reason="safe_typing",
            pending_age_ms=75.0,
            prompt_activity_elapsed_ms=5.0,
            output_activity_elapsed_ms=5.0,
            pending_superseded_count=4,
            stale_safe=True,
        )
    )

    assert decision.delay_ms == policy.idle_delay_ms
    assert decision.force_due_to_max_stale is True
    assert decision.reason == "max_stale"


def test_projection_scheduling_policy_uses_idle_delay_when_not_stale_safe() -> None:
    """Exact or non-safe updates should not be delayed by interaction activity."""

    policy = PromptProjectionSchedulingPolicy()

    decision = policy.choose_delay(
        PromptProjectionScheduleContext(
            reason="prompt_state",
            pending_age_ms=0.0,
            prompt_activity_elapsed_ms=5.0,
            output_activity_elapsed_ms=5.0,
            pending_superseded_count=0,
            stale_safe=False,
        )
    )

    assert decision.delay_ms == policy.idle_delay_ms
    assert decision.force_due_to_max_stale is False
    assert decision.reason == "not_stale_safe"


def test_projection_update_scheduler_preserves_oldest_pending_age_on_supersede() -> (
    None
):
    """Superseded projection batches should age from the first queued update."""

    ensure_qapp()
    now = 10.0
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
    )

    scheduler.schedule(_pending_update_at("alpha", source_revision=1, queued_at=now))
    now += 0.08
    scheduler.schedule(
        _pending_update_at("alpha beta", source_revision=2, queued_at=now)
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
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=applied.append,
        scheduling_policy=policy,
        prompt_activity_elapsed_ms=lambda: 0.0,
        output_activity_elapsed_ms=lambda: None,
    )

    scheduler.schedule(_pending_update("alpha", source_revision=1))
    scheduler._pending_started_at = perf_counter() - 0.08  # noqa: SLF001
    scheduler.schedule(_pending_update("alpha beta", source_revision=2))

    assert scheduler._interval_ms == policy.idle_delay_ms  # noqa: SLF001


def test_projection_update_scheduler_extends_active_typing_timer_on_supersede() -> None:
    """Fresh safe-typing updates should push GUI-thread catch-up past the burst."""

    ensure_qapp()
    policy = PromptProjectionSchedulingPolicy(
        active_typing_delay_ms=180,
        max_stale_ms=750,
    )
    scheduler = PromptProjectionUpdateScheduler(
        apply_update=lambda _update: None,
        scheduling_policy=policy,
        prompt_activity_elapsed_ms=lambda: 0.0,
        output_activity_elapsed_ms=lambda: None,
    )
    timer = _RestartRecordingTimer(remaining_ms=50)
    scheduler._timer = cast(Any, timer)  # noqa: SLF001

    scheduler.schedule(
        _pending_update_at("alpha", source_revision=1, queued_at=perf_counter())
    )
    scheduler.schedule(
        _pending_update_at("alpha beta", source_revision=2, queued_at=perf_counter())
    )

    assert timer.start_calls == [policy.active_typing_delay_ms] * 2
    assert timer.stop_calls == 1
    assert scheduler.has_pending_update() is True


def _pending_update(text: str, *, source_revision: int) -> PendingProjectionUpdate:
    """Build a pending update for scheduler unit tests."""

    return _pending_update_at(text, source_revision=source_revision, queued_at=None)


def _pending_update_at(
    text: str,
    *,
    source_revision: int,
    queued_at: float | None,
) -> PendingProjectionUpdate:
    """Build a pending update with an optional explicit queue time."""

    update = PendingProjectionUpdate.create(
        document_view=PromptDocumentView(
            source_text=text,
            segments=(),
            emphasis_spans=(),
            wildcard_spans=(),
            lora_spans=(),
            syntax_spans=(),
            has_trailing_comma=False,
        ),
        render_plan=PromptSyntaxRenderPlan(
            syntax_spans=(),
            renderer_views=(),
        ),
        reason="test",
        source_revision=source_revision,
    )
    if queued_at is None:
        return update
    return PendingProjectionUpdate(
        document_view=update.document_view,
        render_plan=update.render_plan,
        reason="safe_typing",
        source_revision=update.source_revision,
        queued_at=queued_at,
    )


class _RestartRecordingTimer:
    """Record timer restarts while exposing the QTimer subset under test."""

    def __init__(self, *, remaining_ms: int) -> None:
        """Initialize an inactive fake timer with deterministic remaining time."""

        self.active = False
        self.interval = 0
        self.remaining_ms = remaining_ms
        self.start_calls: list[int] = []
        self.stop_calls = 0

    def setInterval(self, interval: int) -> None:  # noqa: N802
        """Record the interval selected by the scheduler."""

        self.interval = interval

    def isActive(self) -> bool:  # noqa: N802
        """Return whether the fake timer has been started."""

        return self.active

    def start(self, interval: int | None = None) -> None:
        """Record timer starts using the current interval when omitted."""

        self.active = True
        self.start_calls.append(self.interval if interval is None else interval)

    def stop(self) -> None:
        """Record timer stops."""

        self.active = False
        self.stop_calls += 1

    def remainingTime(self) -> int:  # noqa: N802
        """Return deterministic remaining time."""

        return self.remaining_ms


@pytest.fixture
def _projection_surface_scheduler_scope() -> None:
    """Skip surface-backed scheduler tests under Windows xdist workers."""

    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.skip("projection surface tests require non-xdist execution on Windows")


def _flush_projection_update_scheduler(surface: PromptProjectionSurface) -> None:
    """Apply a delayed scheduled projection update through the production scheduler."""

    surface._projection_freshness_controller.update_scheduler.flush_now(reason="test")  # noqa: SLF001


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_default_scheduler_keeps_safe_typing_projection_pending(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default projection scheduling should keep safe typing off the keypress lane."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert box.toPlainText() == "(cat:1.05), x"
    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is True


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_layout_sync_preserves_safe_typing_overlay(
    widgets: list[QWidget],
) -> None:
    """Layout refreshes should not invalidate deferred typed text overlays."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")

    overlay_before_sync = valid_transient_insertion_overlay(surface)
    assert overlay_before_sync is not None
    cast(Any, surface)._sync_layout_state()  # noqa: SLF001
    overlay_after_sync = valid_transient_insertion_overlay(surface)

    assert overlay_after_sync is not None
    assert overlay_after_sync.text == "x"


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_refresh_geometry_does_not_emit_stale_safe_height(
    widgets: list[QWidget],
) -> None:
    """Passive geometry refresh should not publish old height during safe typing."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    emitted_heights: list[float] = []
    surface.contentHeightChanged.connect(emitted_heights.append)

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)
    emitted_heights.clear()
    surface.refresh_geometry()

    assert emitted_heights == []
    assert surface.has_pending_projection_update() is True
    _flush_projection_update_scheduler(surface)


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_schedules_semantics_after_syntax_sensitive_typing(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Token syntax edits should paint immediately and coalesce semantic catch-up."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=240,
    )
    surface = surface_for(box)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "(")

    assert box.toPlainText() == "alpha("
    assert rebuild_count == 0
    assert surface.projection_document().source_text == "alpha("
    assert surface.has_pending_projection_update() is False
    assert surface.has_stale_projection_geometry() is False
    assert surface.cursor_position == len("alpha(")


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_defers_normal_comma_typing(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comma typing in ordinary prompt text should stay off the immediate rebuild path."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, ",")
    overlay = valid_transient_insertion_overlay(surface)
    assert overlay is not None
    assert overlay.text == ","
    flush_semantic_refresh(box)

    assert box.toPlainText() == "alpha,"
    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is True

    _flush_projection_update_scheduler(surface)

    assert rebuild_count == 0
    assert valid_transient_insertion_overlay(surface) is None


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_rebuilds_immediately_for_comma_inside_active_token(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comma typing inside a focused projected syntax token should remain immediate."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    surface.set_cursor_positions(cursor_position=2, anchor_position=2)
    rebuild_count = 0

    QTest.keyClicks(box, ",")

    assert box.toPlainText() == "(c,at:1.05)"
    assert rebuild_count == 0
    assert surface.projection_document().source_text == box.toPlainText()
    assert surface.cursor_position == 3
    assert surface.has_pending_projection_update() is False


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_coalesces_repeated_simple_typed_projection_rebuilds(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated trailing insertions should catch up without full relayout."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "xy")
    overlay = valid_transient_insertion_overlay(surface)
    assert overlay is not None
    assert overlay.text == "xy"
    overlay_rect = cast(Any, surface)._transient_insertion_overlay_viewport_rect(
        overlay
    )
    expected_text_width = QFontMetricsF(box.font()).horizontalAdvance("xy")
    assert overlay_rect.width() == pytest.approx(expected_text_width)
    flush_semantic_refresh(box)

    assert box.toPlainText() == "(cat:1.05), xy"
    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is True

    _flush_projection_update_scheduler(surface)
    process_events(app)

    assert first_emphasis_token(box).display_text == "cat"
    assert surface.projection_document().source_text == "(cat:1.05), xy"
    assert rebuild_count == 0
    assert valid_transient_insertion_overlay(surface) is None


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_cursor_rect_uses_transient_geometry_during_pending_typing(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caret geometry reads during safe typing should not force projection."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0

    assert not box.cursorRect().isNull()

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_ensure_caret_visible_uses_transient_geometry(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caret visibility maintenance during safe typing should not force projection."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)
    surface._ensure_caret_visible()  # noqa: SLF001

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_scheduled_projection_clears_transient_caret_geometry(
    widgets: list[QWidget],
) -> None:
    """Authoritative projection commits should retire temporary caret geometry."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    assert (
        surface._transient_edit_overlays.caret_geometry is not None  # noqa: SLF001
    )

    _flush_projection_update_scheduler(surface)
    process_events(app)

    assert surface.has_pending_projection_update() is False
    assert surface._transient_edit_overlays.caret_geometry is None  # noqa: SLF001


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_hit_testing_flushes_pending_projection_update(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact hit-testing should force pending projection work to apply."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0

    box.cursorForPosition(QPoint(4, 4))

    assert surface.has_pending_projection_update() is False
    assert rebuild_count == 0


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_hover_move_does_not_flush_pending_projection_update(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hover tracking must not force safe-typing projection work onto mouse move."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    flush_count = 0

    def count_flush(*, reason: str) -> None:
        """Record unexpected mouse-move flushes without applying them."""

        nonlocal flush_count
        del reason
        flush_count += 1

    monkeypatch.setattr(surface, "_flush_pending_projection_update", count_flush)
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(4.0, 4.0),
        QPointF(4.0, 4.0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(surface.viewport(), event)

    assert flush_count == 0
    assert surface.has_pending_projection_update() is True


@pytest.mark.usefixtures("_projection_surface_scheduler_scope")
def test_projection_surface_resize_does_not_flush_pending_projection_update(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resize should reflow prepared geometry without forcing stale-safe projection."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    flush_calls: list[str] = []
    rebuild_count = 0

    def record_flush(*, reason: str) -> None:
        """Record an unexpected resize projection flush."""

        flush_calls.append(reason)

    def record_rebuild() -> None:
        """Record an unexpected resize projection rebuild."""

        nonlocal rebuild_count
        rebuild_count += 1

    monkeypatch.setattr(surface, "_flush_pending_projection_update", record_flush)
    monkeypatch.setattr(surface, "_rebuild_projection", record_rebuild)

    surface.resize(surface.width() + 24, surface.height() + 8)
    process_events(ensure_qapp())

    assert flush_calls == []
    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is True
