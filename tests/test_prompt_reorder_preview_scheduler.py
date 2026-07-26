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
from collections.abc import Callable
from typing import cast

import pytest
from PySide6.QtCore import QTimer

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.reorder.views import PromptReorderLayoutView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_preview_timer import (
    PromptReorderPreviewTimer,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_preview_sync import (
    PromptReorderPreviewSyncController,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_preview_publication import (
    PromptReorderPreviewPublicationOwner,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_projection_snapshot_provider import (
    PromptReorderPreviewProjectionProvider,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.prompt_reorder_interaction_test_helpers import (
    ControllerEditorDouble,
    FakeQTimer,
    MenuCursorDouble,
    OverlayDouble,
    PreviewSyncContextDouble,
)


def test_segment_overlay_preview_sync_is_latest_wins() -> None:
    """Repeated overlay preview changes coalesce until an explicit flush."""

    preview, editor = _publication_owner_for_text("alpha, beta")

    preview.schedule()
    preview.schedule(reason="drag_move")
    preview.schedule(reason="drag_move")

    assert editor.clear_reorder_preview_state_calls == 0
    preview_sync_state = preview.state
    assert preview_sync_state.pending_revision == 3
    assert preview_sync_state.pending_reason == "drag_move"

    preview.flush()

    assert editor.clear_reorder_preview_state_calls == 1
    preview_sync_state = preview.state
    assert preview_sync_state.pending_revision is None
    assert preview_sync_state.pending_reason is None
    assert preview_sync_state.last_applied_revision == 3


def test_segment_overlay_preview_sync_schedules_when_base_geometry_is_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drag preview sync stays exact but scheduled after hit-test geometry exists."""

    reorder_mod = importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.reorder_preview_timer"
    )
    FakeQTimer.instances.clear()
    monkeypatch.setattr(reorder_mod, "QTimer", FakeQTimer)
    metrics = PromptReorderInteractionMetricsOwner()
    preview, _editor = _publication_owner_for_text(
        "alpha, beta",
        metrics=metrics,
    )
    layout_view = _reorder_layout_view_for_text("alpha, beta")
    overlay = OverlayDouble(
        dragged_segment_index=1,
        base_drag_layout_view=layout_view,
        has_base_drag_placement_geometry=True,
    )
    preview.bind_session(
        overlay=overlay,
        build_facts=overlay,
        sync_context=PreviewSyncContextDouble(overlay, metrics),
    )
    preview.schedule(reason="drag_move")

    assert overlay.autoscroll_flush_calls == []
    preview_sync_state = preview.state
    assert preview_sync_state.pending_revision == 1
    assert preview_sync_state.scheduler_active is True
    assert FakeQTimer.instances[-1].started_intervals == [
        PromptReorderPreviewPublicationOwner.DEFAULT_INTERVAL_MS
    ]
    assert metrics.snapshot().preview_sync_deferred_count == 1


def test_segment_overlay_preview_sync_is_immediate_when_base_geometry_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drag preview sync flushes immediately until hit-test geometry exists."""

    metrics = PromptReorderInteractionMetricsOwner()
    preview, _editor = _publication_owner_for_text(
        "alpha, beta",
        metrics=metrics,
    )
    layout_view = _reorder_layout_view_for_text("alpha, beta")
    overlay = OverlayDouble(
        dragged_segment_index=1,
        base_drag_layout_view=layout_view,
        has_base_drag_placement_geometry=False,
    )
    preview.bind_session(
        overlay=overlay,
        build_facts=overlay,
        sync_context=PreviewSyncContextDouble(overlay, metrics),
    )
    preview.schedule(reason="drag_start")

    assert overlay.autoscroll_flush_calls == ["autoscroll_coalesced_preview_sync"]
    assert preview.state.pending_revision is None
    assert metrics.snapshot().preview_sync_immediate_count == 1


def test_segment_overlay_preview_sync_defers_initial_shadow_within_one_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing first shadow should not block the pointer event that starts drag."""

    metrics = PromptReorderInteractionMetricsOwner()
    preview, _editor = _publication_owner_for_text(
        "alpha, beta",
        metrics=metrics,
    )
    layout_view = _reorder_layout_view_for_text("alpha, beta")
    overlay = OverlayDouble(
        dragged_segment_index=1,
        base_drag_layout_view=layout_view,
        has_base_drag_placement_geometry=True,
        should_flush_initial_landing_shadow_sync=True,
    )
    preview.bind_session(
        overlay=overlay,
        build_facts=overlay,
        sync_context=PreviewSyncContextDouble(overlay, metrics),
    )
    preview.schedule(reason="drag_start")
    preview.schedule(reason="drag_move")

    assert overlay.autoscroll_flush_calls == []
    assert preview.state.pending_revision == 2
    assert metrics.snapshot().preview_sync_deferred_count == 2


def test_segment_overlay_preview_sync_skips_stale_pending_revision() -> None:
    """A stale scheduled preview revision does not run expensive sync work."""

    sync_calls = 0

    def record_sync() -> None:
        """Record unexpected expensive preview sync executions."""

        nonlocal sync_calls
        sync_calls += 1

    preview_sync = PromptReorderPreviewSyncController(
        interval_ms=16,
        run_sync=record_sync,
        timer_factory=cast(Callable[[], QTimer], FakeQTimer),
    )
    preview_sync.replace_state(
        pending_revision=3,
        pending_reason="drag_move",
        last_applied_revision=4,
    )

    preview_sync.flush_pending()

    assert sync_calls == 0
    preview_sync_state = preview_sync.state
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

    scheduler = PromptReorderPreviewTimer(
        interval_ms=16,
        run_pending=run_pending,
        timer_factory=cast(Callable[[], QTimer], FakeQTimer),
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

    scheduler = PromptReorderPreviewTimer(
        interval_ms=16,
        run_pending=run_pending,
        timer_factory=cast(Callable[[], QTimer], FakeQTimer),
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


def _publication_owner_for_text(
    text: str,
    *,
    metrics: PromptReorderInteractionMetricsOwner | None = None,
) -> tuple[PromptReorderPreviewPublicationOwner, ControllerEditorDouble]:
    """Build the real preview owner with only its owned projection ports."""

    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text=text, position=7),
        current_cursor=MenuCursorDouble(text=text, position=7),
        text=text,
    )
    document_service = PromptDocumentService()
    resolved_metrics = metrics or PromptReorderInteractionMetricsOwner()
    owner = PromptReorderPreviewPublicationOwner(
        clear_preview_state=editor.clear_reorder_preview_state,
        current_document_view=lambda: document_service.build_document_view(text),
        publish_preview_state=editor.set_reorder_preview_state,
        source_identity=editor.prompt_command_source_identity,
        viewport_width=lambda: 0,
        document_service=document_service,
        projection_provider=PromptReorderPreviewProjectionProvider(
            document_service=document_service,
            syntax_service=PromptSyntaxService(EmptyPromptWildcardCatalogGateway()),
            syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        ),
        metrics=resolved_metrics,
        interval_ms=PromptReorderPreviewPublicationOwner.DEFAULT_INTERVAL_MS,
    )
    return owner, editor


def _reorder_layout_view_for_text(text: str) -> PromptReorderLayoutView:
    """Build the application reorder layout view for sample prompt text."""

    document_service = PromptDocumentService()
    return document_service.build_reorder_layout_view(
        document_service.build_document_view(text)
    )
