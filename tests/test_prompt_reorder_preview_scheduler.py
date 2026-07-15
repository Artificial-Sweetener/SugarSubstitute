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

"""Tests for prompt reorder preview scheduler orchestration."""

from __future__ import annotations

import importlib
from typing import Any

import pytest

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptMutationService,
    PromptReorderLayoutView,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_preview_sync import (
    PromptReorderPreviewScheduler,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile
from tests.prompt_reorder_interaction_test_helpers import (
    ControllerEditorDouble,
    FakeQTimer,
    MenuCursorDouble,
    OverlayDouble,
    autocomplete_double,
    prompt_interaction_controller,
    semantic_refresh_controller_double,
    syntax_renderer_double,
    syntax_service,
)


def test_segment_overlay_preview_sync_is_latest_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated overlay preview changes coalesce until an explicit flush."""

    controller = _controller_for_reorder_text("alpha, beta")
    sync_calls = 0

    def record_sync() -> None:
        """Record actual expensive preview sync executions."""

        nonlocal sync_calls
        sync_calls += 1

    monkeypatch.setattr(
        controller._reorder,
        "_sync_reorder_preview_from_overlay",
        record_sync,
    )

    controller._reorder.schedule_reorder_preview_sync()
    controller._reorder.schedule_reorder_preview_sync(reason="drag_move")
    controller._reorder.schedule_reorder_preview_sync(reason="drag_move")

    assert sync_calls == 0
    preview_sync_state = controller._reorder._preview_sync.state
    assert preview_sync_state.pending_revision == 3
    assert preview_sync_state.pending_reason == "drag_move"

    controller._reorder.flush_pending_reorder_preview_sync()

    assert sync_calls == 1
    preview_sync_state = controller._reorder._preview_sync.state
    assert preview_sync_state.pending_revision is None
    assert preview_sync_state.pending_reason is None
    assert preview_sync_state.last_applied_revision == 3


def test_segment_overlay_preview_sync_schedules_when_base_geometry_is_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drag preview sync stays exact but scheduled after hit-test geometry exists."""

    reorder_mod = importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.reorder_preview_sync"
    )
    FakeQTimer.instances.clear()
    monkeypatch.setattr(reorder_mod, "QTimer", FakeQTimer)
    controller = _controller_for_reorder_text("alpha, beta")
    layout_view = _reorder_layout_view_for_text("alpha, beta")
    overlay = OverlayDouble(
        dragged_segment_index=1,
        base_drag_layout_view=layout_view,
        has_base_drag_placement_geometry=True,
    )
    controller._reorder._segment_overlay = overlay
    sync_calls = 0

    def record_sync() -> None:
        """Record unexpected immediate sync executions."""

        nonlocal sync_calls
        sync_calls += 1

    monkeypatch.setattr(
        controller._reorder,
        "_sync_reorder_preview_from_overlay",
        record_sync,
    )

    controller._reorder.schedule_reorder_preview_sync(reason="drag_move")

    assert sync_calls == 0
    preview_sync_state = controller._reorder._preview_sync.state
    assert preview_sync_state.pending_revision == 1
    assert preview_sync_state.scheduler_active is True
    assert FakeQTimer.instances[-1].started_intervals == [
        controller._reorder._REORDER_PREVIEW_SYNC_INTERVAL_MS
    ]
    assert overlay.preview_sync_decisions == [False]


def test_segment_overlay_preview_sync_is_immediate_when_base_geometry_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drag preview sync flushes immediately until hit-test geometry exists."""

    controller = _controller_for_reorder_text("alpha, beta")
    layout_view = _reorder_layout_view_for_text("alpha, beta")
    overlay = OverlayDouble(
        dragged_segment_index=1,
        base_drag_layout_view=layout_view,
        has_base_drag_placement_geometry=False,
    )
    controller._reorder._segment_overlay = overlay
    sync_calls = 0

    def record_sync() -> None:
        """Record immediate sync executions."""

        nonlocal sync_calls
        sync_calls += 1

    monkeypatch.setattr(
        controller._reorder,
        "_sync_reorder_preview_from_overlay",
        record_sync,
    )

    controller._reorder.schedule_reorder_preview_sync(reason="drag_start")

    assert sync_calls == 1
    assert controller._reorder._preview_sync.state.pending_revision is None
    assert overlay.preview_sync_decisions == [True]


def test_segment_overlay_preview_sync_flushes_initial_shadow_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first missing chip-shaped shadow may force one sync after base geometry."""

    controller = _controller_for_reorder_text("alpha, beta")
    layout_view = _reorder_layout_view_for_text("alpha, beta")
    overlay = OverlayDouble(
        dragged_segment_index=1,
        base_drag_layout_view=layout_view,
        has_base_drag_placement_geometry=True,
        should_flush_initial_landing_shadow_sync=True,
    )
    controller._reorder._segment_overlay = overlay
    sync_calls = 0

    def record_sync() -> None:
        """Record immediate sync executions."""

        nonlocal sync_calls
        sync_calls += 1

    monkeypatch.setattr(
        controller._reorder,
        "_sync_reorder_preview_from_overlay",
        record_sync,
    )

    controller._reorder.schedule_reorder_preview_sync(reason="drag_start")
    controller._reorder.schedule_reorder_preview_sync(reason="drag_move")

    assert sync_calls == 1
    assert controller._reorder._preview_sync.state.pending_revision == 2
    assert overlay.preview_sync_decisions == [True, False]


def test_segment_overlay_preview_sync_skips_stale_pending_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale scheduled preview revision does not run expensive sync work."""

    controller = _controller_for_reorder_text("alpha, beta")
    sync_calls = 0

    def record_sync() -> None:
        """Record unexpected expensive preview sync executions."""

        nonlocal sync_calls
        sync_calls += 1

    monkeypatch.setattr(
        controller._reorder,
        "_sync_reorder_preview_from_overlay",
        record_sync,
    )
    controller._reorder._preview_sync.replace_state(
        pending_revision=3,
        pending_reason="drag_move",
        last_applied_revision=4,
    )

    controller._reorder.flush_pending_reorder_preview_sync()

    assert sync_calls == 0
    preview_sync_state = controller._reorder._preview_sync.state
    assert preview_sync_state.pending_revision is None
    assert preview_sync_state.pending_reason is None


def test_reorder_preview_scheduler_skips_coalesced_stale_revisions() -> None:
    """Latest-wins scheduling explicitly drops older pending revisions."""

    FakeQTimer.instances.clear()
    run_calls = 0
    events: list[str] = []

    def run_pending() -> None:
        """Record one scheduler-approved preview run."""

        nonlocal run_calls
        run_calls += 1

    scheduler = PromptReorderPreviewScheduler(
        interval_ms=16,
        run_pending=run_pending,
        timer_factory=FakeQTimer,
        record_event=events.append,
    )

    scheduler.request(
        revision=1,
        reason="drag_move",
        pointer_active=True,
        gesture_id=10,
        event_id=20,
    )
    scheduler.request(
        revision=2,
        reason="drag_move",
        pointer_active=True,
        gesture_id=10,
        event_id=21,
    )
    FakeQTimer.instances[-1].fire()

    assert run_calls == 1
    assert "skipped_stale" in events
    assert events.count("ran_latest") == 1


def test_reorder_preview_scheduler_reschedules_after_pointer_motion() -> None:
    """Pointer movement after a request defers preview work before the cap."""

    FakeQTimer.instances.clear()
    pointer_revision = 1
    run_calls = 0
    events: list[str] = []

    def current_pointer_revision() -> int:
        """Return the mutable pointer revision used by the scheduler."""

        return pointer_revision

    def run_pending() -> None:
        """Record one scheduler-approved preview run."""

        nonlocal run_calls
        run_calls += 1

    scheduler = PromptReorderPreviewScheduler(
        interval_ms=16,
        run_pending=run_pending,
        timer_factory=FakeQTimer,
        pointer_revision=current_pointer_revision,
        record_event=events.append,
    )

    scheduler.request(
        revision=1,
        reason="drag_move",
        pointer_active=True,
        gesture_id=10,
        event_id=20,
    )
    pointer_revision = 2
    FakeQTimer.instances[-1].fire()

    assert run_calls == 0
    assert "rescheduled_after_pointer" in events
    assert FakeQTimer.instances[-1].isActive()

    FakeQTimer.instances[-1].fire()

    assert run_calls == 1
    assert events.count("ran_latest") == 1


def _controller_for_reorder_text(text: str) -> Any:
    """Build a prompt interaction controller positioned in sample prompt text."""

    return prompt_interaction_controller(
        ControllerEditorDouble(
            clicked_cursor=MenuCursorDouble(text=text, position=7),
            current_cursor=MenuCursorDouble(text=text, position=7),
            text=text,
        ),
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderer_double(),
        document_service=PromptDocumentService(),
        mutation_service=PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
    )


def _reorder_layout_view_for_text(text: str) -> PromptReorderLayoutView:
    """Build the application reorder layout view for sample prompt text."""

    document_service = PromptDocumentService()
    return document_service.build_reorder_layout_view(
        document_service.build_document_view(text)
    )
