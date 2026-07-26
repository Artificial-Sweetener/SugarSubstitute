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

"""Test prompt-editor abuse tool models, orchestration, and reporting."""

from __future__ import annotations

import gc
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSizeF
import pytest

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from tools.prompt_editor_abuse import reorder_action_host
from tools.prompt_editor_abuse.action_counter_probe import (
    PromptAbuseActionCounterProbe,
)
from tools.prompt_editor_abuse.campaign import run_campaign
from tools.prompt_editor_abuse.comparison import (
    compare_report_files,
    format_comparison,
)
from tools.prompt_editor_abuse.coverage import capture_operation_coverage
from tools.prompt_editor_abuse.models import (
    PromptAbuseAction,
    PromptAbuseActionOwnerDelta,
    PromptAbuseDispatchSample,
    PromptAbuseCampaignReport,
    PromptAbuseLatencyBreakdown,
    PromptAbuseLatencySummary,
    PromptAbuseScenario,
    PromptAbuseScenarioResult,
    PromptAbuseSystemLoad,
)
from tools.prompt_editor_abuse.minimization import truncate_scenario_to_sample
from tools.prompt_editor_abuse.reporting import format_summary, write_report
from tools.prompt_editor_abuse.replay import load_report_scenarios, scenario_prefix
from tools.prompt_editor_abuse.runtime_probe import PromptAbuseRuntimeProbe
from tools.prompt_editor_abuse.qt_exception_capture import (
    PromptAbuseQtExceptionCapture,
)
from tools.prompt_editor_abuse.reorder_action_host import (
    PromptReorderAbuseActionHost,
)
from tools.prompt_editor_abuse.statistics import percentile, summarize_latencies
from tools.prompt_editor_abuse.structural_policy import (
    prompt_abuse_structural_violations,
)
from tools.prompt_editor_abuse.structural_instrumentation import (
    prompt_abuse_structural_instrumentation,
)
from tools.prompt_editor_abuse.workloads import KEY_SLAM, hostile_prompt_scenarios


def test_reorder_host_resolves_destination_after_drag_start_settles_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Back-to-back drags should target geometry established at drag start."""

    class _Overlay:
        """Expose identity coordinate mapping for the harness action host."""

        def __init__(self) -> None:
            """Initialize the typed drag-base query returned to the host."""

            self.base_drag_layout: object | None = None

        def base_drag_layout_view(self) -> object | None:
            """Return the drag-base layout through the production query shape."""

            return self.base_drag_layout

        @staticmethod
        def mapToGlobal(point: QPoint) -> QPoint:
            """Return an identity-mapped global point."""

            return QPoint(point)

        @staticmethod
        def mapFromGlobal(point: QPoint) -> QPoint:
            """Return an identity-mapped overlay point."""

            return QPoint(point)

    overlay: Any = _Overlay()
    destination = PromptLineDropTarget(row_index=7, insertion_index=0)
    placement = SimpleNamespace(
        target=destination,
        hit_rect=QRectF(400.0, 50.0, 20.0, 20.0),
    )

    def placement_for_target(target: object) -> SimpleNamespace | None:
        """Return the one semantic placement owned by the fake snapshot."""

        return placement if target == destination else None

    overlay.base_drag_layout = SimpleNamespace(
        rows=(SimpleNamespace(row_index=7, chip_indices=(0,)),)
    )
    overlay.preview_build_facts = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(base_drag_layout_view=overlay.base_drag_layout)
    )
    overlay._geometry = SimpleNamespace(
        state=SimpleNamespace(
            placement_snapshot=SimpleNamespace(
                placement_for_target=placement_for_target
            )
        )
    )
    overlay._gesture = SimpleNamespace(
        state=SimpleNamespace(
            drag_intent_size=QSizeF(40.0, 20.0),
            drag_grab_offset=QPointF(20.0, 10.0),
        )
    )
    pressed = False
    drag_started = False

    def chip_target(_overlay: object, segment_index: int) -> SimpleNamespace:
        """Return destination geometry that moves when press settles animation."""

        if segment_index == 1:
            rect = QRect(10, 10, 40, 20)
        else:
            left = 300 if drag_started else 200 if pressed else 100
            rect = QRect(left, 50, 40, 20)
        return SimpleNamespace(overlay=_overlay, segment_index=segment_index, rect=rect)

    def press(*_args: object, **_kwargs: object) -> None:
        """Model production settling the previous animation on pointer press."""

        nonlocal pressed
        pressed = True

    def move(*_args: object, **_kwargs: object) -> None:
        """Model threshold crossing establishing stable base drag geometry."""

        nonlocal drag_started
        drag_started = True

    monkeypatch.setattr(reorder_action_host, "overlay_chip", chip_target)
    monkeypatch.setattr(
        reorder_action_host,
        "QTest",
        SimpleNamespace(mousePress=press, mouseMove=move),
    )
    monkeypatch.setattr(
        reorder_action_host,
        "QApplication",
        SimpleNamespace(startDragDistance=lambda: 10),
    )
    host = PromptReorderAbuseActionHost()

    host.reorder_drag_press(SimpleNamespace(_segment_overlay=overlay), "1:0")
    host.reorder_drag_threshold(SimpleNamespace(_segment_overlay=overlay))

    assert host._target == QPoint(410, 60)  # noqa: SLF001


def test_runtime_probe_attributes_gc_without_changing_collection_policy() -> None:
    """Harness telemetry should observe GC without suppressing or forcing policy."""

    enabled_before = gc.isenabled()
    callbacks_before = tuple(gc.callbacks)
    with PromptAbuseRuntimeProbe(enabled=True) as probe:
        probe.begin_sample()
        gc.collect()
        sample = probe.finish_sample()

    assert sample.gc_collection_count == 1
    assert sample.gc_pause_ms >= 0.0
    assert gc.isenabled() is enabled_before
    assert tuple(gc.callbacks) == callbacks_before


def test_qt_exception_capture_turns_uncaught_callbacks_into_violations() -> None:
    """Delayed callback failures should make harness correctness fail closed."""

    with PromptAbuseQtExceptionCapture() as capture:
        sys.excepthook(RuntimeError, RuntimeError("delayed preview failed"), None)

    assert capture.violations == (
        "uncaught_qt_callback:RuntimeError:delayed preview failed",
    )


def test_action_counter_probe_attributes_created_and_closed_overlay_work() -> None:
    """Deep traces should retain per-action counters across overlay lifecycle."""

    class _Overlay:
        """Expose mutable production-shaped performance counters."""

        def __init__(self) -> None:
            """Initialize an idle owner counter snapshot."""

            self.counters = {"raster_build_count": 0, "drag_move_count": 0}

        def reorder_performance_counters(self) -> dict[str, object]:
            """Return a copy of the current counter state."""

            return dict(self.counters)

    editor = SimpleNamespace(_segment_overlay=None)
    probe = PromptAbuseActionCounterProbe(editor)
    overlay = _Overlay()

    probe.begin_unit()
    editor._segment_overlay = overlay
    overlay.counters["raster_build_count"] = 8
    opened = probe.finish_unit(action_index=2, unit_index=0, label="key_press:alt")

    probe.begin_unit()
    overlay.counters["drag_move_count"] = 3
    editor._segment_overlay = None
    closed = probe.finish_unit(action_index=3, unit_index=0, label="key_release:alt")

    assert dict(opened.counter_deltas) == {"raster_build_count": 8.0}
    assert dict(closed.counter_deltas) == {"drag_move_count": 3.0}
    assert opened.reset_counter_names == ()
    assert closed.reset_counter_names == ()

    editor._segment_overlay = overlay
    overlay.counters["drag_move_count"] = 9
    probe.begin_unit()
    overlay.counters["drag_move_count"] = 1
    reset = probe.finish_unit(action_index=4, unit_index=0, label="owner_reset")
    assert reset.counter_deltas == ()
    assert reset.reset_counter_names == ("drag_move_count",)


def test_structural_policy_accepts_bounded_pointer_and_coalesced_preview_work() -> None:
    """Owner budgets should accept geometry-only moves and one queued preview unit."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=4,
            unit_index=0,
            label="reorder_drag_move:0.500000",
            counter_deltas=(
                ("autoscroll_pointer_update_count", 1.0),
                ("drag_move_count", 1.0),
                ("drop_target_changed_count", 1.0),
                ("instrumented_reorder_preview_request_count", 1.0),
                ("max_drag_move_ms", 2.5),
                ("preview_scheduler_request_count", 1.0),
                ("target_change_count", 1.0),
            ),
        ),
        PromptAbuseActionOwnerDelta(
            action_index=5,
            unit_index=0,
            label="event_turn:",
            counter_deltas=(
                ("animation_plan_applied_count", 1.0),
                ("animation_plan_build_count", 1.0),
                ("preview_geometry_full_count", 1.0),
                ("preview_projection_incremental_layout_count", 2.0),
                ("preview_scheduler_run_count", 1.0),
                ("projection_snapshot_rebuild_count", 2.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(deltas) == ()


def test_structural_policy_rejects_duplicate_reorder_activation_geometry() -> None:
    """Alt activation must prepare one coherent preview geometry publication."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="key_press:'alt'",
            counter_deltas=(("preview_geometry_full_count", 2.0),),
        ),
    )

    violations = prompt_abuse_structural_violations(deltas)

    assert len(violations) == 1
    assert "preview_geometry_full_count" in violations[0]
    assert "expected=<=1" in violations[0]
    assert "actual=2" in violations[0]


def test_structural_policy_rejects_heavy_pointer_work_and_unbounded_queueing() -> None:
    """Direct pointer work and queued publication should fail with exact diagnostics."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=4,
            unit_index=0,
            label="reorder_drag_move:1.000000",
            counter_deltas=(
                ("drag_move_count", 1.0),
                ("drop_target_changed_count", 1.0),
                ("instrumented_reorder_preview_request_count", 2.0),
                ("preview_scheduler_request_count", 2.0),
                ("projection_snapshot_rebuild_count", 1.0),
                ("target_change_count", 1.0),
            ),
        ),
        PromptAbuseActionOwnerDelta(
            action_index=5,
            unit_index=0,
            label="event_turn:",
            counter_deltas=(
                ("preview_scheduler_run_count", 2.0),
                ("projection_snapshot_rebuild_count", 3.0),
            ),
        ),
    )

    violations = prompt_abuse_structural_violations(deltas)

    assert any("preview_scheduler_request_count" in item for item in violations)
    assert any("projection_snapshot_rebuild_count" in item for item in violations)
    assert any("preview_scheduler_run_count" in item for item in violations)
    assert all(item.startswith("structural_budget:") for item in violations)


def test_structural_policy_rejects_editor_rebuild_work_on_canvas_round_trip() -> None:
    """Canvas switching must not rebuild or prepare hidden prompt-editor state."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=2,
            unit_index=0,
            label="canvas_round_trip:",
            counter_deltas=(
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_rebuild_count", 1.0),
                ("region_chrome_prepare_count", 1.0),
            ),
        ),
    )

    violations = prompt_abuse_structural_violations(deltas)

    assert len(violations) == 3
    assert any("instrumented_layout_snapshot_count" in item for item in violations)
    assert any("instrumented_projection_rebuild_count" in item for item in violations)
    assert any("region_chrome_prepare_count" in item for item in violations)


def test_structural_policy_rejects_semantic_work_on_passive_editor_actions() -> None:
    """Navigation, selection, paint, and scroll must remain source-neutral."""

    deltas = tuple(
        PromptAbuseActionOwnerDelta(
            action_index=index,
            unit_index=0,
            label=label,
            counter_deltas=(
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_surface_source_apply_count", 1.0),
            ),
        )
        for index, label in enumerate(
            (
                "key:'up'",
                "mouse_caret",
                "mouse_drag_selection",
                "move_cursor",
                "request_paint",
                "scroll",
                "select",
            )
        )
    )

    violations = prompt_abuse_structural_violations(deltas)

    assert len(violations) == len(deltas) * 3
    assert all("expected=0" in violation for violation in violations)


def test_structural_policy_accepts_one_bounded_incremental_user_edit() -> None:
    """One character edit may use one source and one projection strategy."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="type:'x'",
            counter_deltas=(
                ("instrumented_editing_replace_range_count", 1.0),
                ("instrumented_projection_incremental_applied_count", 1.0),
                ("instrumented_surface_source_apply_count", 1.0),
            ),
        ),
        PromptAbuseActionOwnerDelta(
            action_index=1,
            unit_index=0,
            label="key:'enter'",
            counter_deltas=(
                ("instrumented_editing_replace_range_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 1.0),
                ("instrumented_projection_rebuild_count", 1.0),
                ("instrumented_surface_source_apply_count", 1.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(deltas) == ()


def test_structural_policy_distinguishes_canonical_and_active_edit_projections() -> (
    None
):
    """One canonical edit may publish one additional active-edit projection."""

    accepted = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="type:')'",
            counter_deltas=(
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 2.0),
                ("instrumented_syntax_render_plan_build_count", 1.0),
            ),
        ),
    )
    rejected = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="type:')'",
            counter_deltas=(
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 3.0),
                ("instrumented_syntax_render_plan_build_count", 1.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(accepted) == ()
    assert any(
        "instrumented_projection_document_build_count" in violation
        for violation in prompt_abuse_structural_violations(rejected)
    )


def test_structural_policy_models_one_immediate_danbooru_import_completion() -> None:
    """Literal URL paste and its immediate import may commit two revisions."""

    accepted = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="paste:'https://danbooru.donmai.us/posts/1'",
            counter_deltas=(
                ("instrumented_danbooru_import_apply_count", 1.0),
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_editing_replace_range_count", 2.0),
                ("instrumented_editing_paste_count", 1.0),
                ("instrumented_projection_document_build_count", 2.0),
                ("instrumented_surface_source_apply_count", 2.0),
                ("instrumented_syntax_render_plan_build_count", 1.0),
            ),
        ),
    )
    rejected = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="paste:'https://danbooru.donmai.us/posts/1'",
            counter_deltas=(
                ("instrumented_danbooru_import_apply_count", 2.0),
                ("instrumented_editing_replace_range_count", 3.0),
                ("instrumented_surface_source_apply_count", 3.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(accepted) == ()
    violations = prompt_abuse_structural_violations(rejected)
    assert any(
        "instrumented_danbooru_import_apply_count" in item for item in violations
    )
    assert any(
        "instrumented_editing_replace_range_count" in item for item in violations
    )
    assert any("instrumented_surface_source_apply_count" in item for item in violations)


def test_structural_policy_rejects_duplicate_edit_and_projection_work() -> None:
    """One input unit must not trigger multiple source or applied-path units."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="paste:'x'",
            counter_deltas=(
                ("instrumented_editing_paste_count", 2.0),
                ("instrumented_editing_replace_full_source_count", 1.0),
                ("instrumented_editing_replace_range_count", 2.0),
                ("instrumented_projection_fast_insert_applied_count", 1.0),
                ("instrumented_projection_incremental_applied_count", 1.0),
                ("instrumented_surface_source_apply_count", 2.0),
            ),
        ),
    )

    violations = prompt_abuse_structural_violations(deltas)

    assert any("instrumented_editing_paste_count" in item for item in violations)
    assert any(
        "instrumented_editing_replace_full_source_count" in item for item in violations
    )
    assert any(
        "instrumented_editing_replace_range_count" in item for item in violations
    )
    assert any("instrumented_surface_source_apply_count" in item for item in violations)
    assert any("projection_applied_path_count" in item for item in violations)


def test_structural_policy_bounds_queued_core_and_workflow_round_trip_work() -> None:
    """One event turn and one workflow round trip must stay coalesced."""

    accepted = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="event_turn:0",
            counter_deltas=(
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 1.0),
                ("instrumented_projection_rebuild_count", 1.0),
                ("instrumented_syntax_render_plan_build_count", 1.0),
                ("region_chrome_prepare_count", 1.0),
            ),
        ),
        PromptAbuseActionOwnerDelta(
            action_index=1,
            unit_index=0,
            label="workflow_round_trip",
            counter_deltas=(
                ("instrumented_document_view_build_count", 2.0),
                ("instrumented_editing_replace_full_source_count", 1.0),
                ("instrumented_layout_snapshot_count", 6.0),
                ("instrumented_projection_document_build_count", 4.0),
                ("instrumented_projection_rebuild_count", 2.0),
                ("instrumented_syntax_render_plan_build_count", 2.0),
            ),
        ),
    )
    rejected = tuple(
        PromptAbuseActionOwnerDelta(
            action_index=delta.action_index,
            unit_index=delta.unit_index,
            label=delta.label,
            counter_deltas=tuple(
                (counter_name, value + 1.0)
                for counter_name, value in delta.counter_deltas
            ),
        )
        for delta in accepted
    )

    assert prompt_abuse_structural_violations(accepted) == ()
    violations = prompt_abuse_structural_violations(rejected)
    assert len(violations) == 12


def test_structural_policy_models_queued_autocomplete_and_reorder_projections() -> None:
    """Queued transient owners may add bounded projection and layout documents."""

    deltas = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="drain_events:0",
            counter_deltas=(
                ("instrumented_autocomplete_preview_update_count", 1.0),
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_layout_snapshot_count", 2.0),
                ("instrumented_projection_document_build_count", 2.0),
                ("instrumented_syntax_render_plan_build_count", 1.0),
            ),
        ),
        PromptAbuseActionOwnerDelta(
            action_index=1,
            unit_index=0,
            label="event_turn:0",
            counter_deltas=(
                ("instrumented_document_view_build_count", 2.0),
                ("instrumented_layout_snapshot_count", 4.0),
                ("instrumented_projection_document_build_count", 2.0),
                ("instrumented_reorder_preview_run_count", 1.0),
                ("instrumented_syntax_render_plan_build_count", 2.0),
                ("preview_scheduler_run_count", 1.0),
            ),
        ),
        PromptAbuseActionOwnerDelta(
            action_index=2,
            unit_index=0,
            label="key:'down'",
            counter_deltas=(
                ("instrumented_autocomplete_preview_update_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 1.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(deltas) == ()


def test_structural_policy_attributes_deferred_projection_flush_to_prior_edit() -> None:
    """Passive movement may flush one explicitly identified pending edit update."""

    accepted = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="move_cursor",
            counter_deltas=(
                ("instrumented_diagnostic_cache_clear_count", 1.0),
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 1.0),
                ("instrumented_projection_pending_flush_applied_count", 1.0),
                ("instrumented_projection_rebuild_count", 1.0),
            ),
        ),
    )
    unowned_rebuild = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="move_cursor",
            counter_deltas=(
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_projection_document_build_count", 1.0),
                ("instrumented_projection_rebuild_count", 1.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(accepted) == ()
    assert len(prompt_abuse_structural_violations(unowned_rebuild)) == 3


def test_structural_policy_attributes_passive_diagnostic_cache_clear_to_publish() -> (
    None
):
    """Caret movement may invalidate one materially changed diagnostic view."""

    accepted = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="select",
            counter_deltas=(
                ("instrumented_diagnostic_cache_clear_count", 1.0),
                ("instrumented_diagnostics_visible_publish_count", 1.0),
                ("instrumented_diagnostics_visible_refresh_count", 2.0),
            ),
        ),
    )
    unowned_clear = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="select",
            counter_deltas=(
                ("instrumented_diagnostic_cache_clear_count", 1.0),
                ("instrumented_diagnostics_visible_refresh_count", 1.0),
            ),
        ),
    )
    repeated_publish = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="move_cursor",
            counter_deltas=(
                ("instrumented_diagnostic_cache_clear_count", 2.0),
                ("instrumented_diagnostics_visible_publish_count", 2.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(accepted) == ()
    assert len(prompt_abuse_structural_violations(unowned_clear)) == 1
    assert len(prompt_abuse_structural_violations(repeated_publish)) == 2


def test_structural_policy_keeps_resize_source_neutral_and_single_pass() -> None:
    """A delivered resize may lay out once without rebuilding prompt semantics."""

    accepted = (
        PromptAbuseActionOwnerDelta(
            action_index=0,
            unit_index=0,
            label="resize",
            counter_deltas=(
                ("instrumented_layout_snapshot_count", 1.0),
                ("instrumented_surface_resize_event_count", 1.0),
                ("region_chrome_prepare_count", 1.0),
            ),
        ),
    )
    rejected = (
        PromptAbuseActionOwnerDelta(
            action_index=1,
            unit_index=0,
            label="resize",
            counter_deltas=(
                ("instrumented_document_view_build_count", 1.0),
                ("instrumented_layout_snapshot_count", 2.0),
                ("instrumented_projection_rebuild_count", 1.0),
                ("instrumented_surface_resize_event_count", 2.0),
            ),
        ),
    )

    assert prompt_abuse_structural_violations(accepted) == ()
    violations = prompt_abuse_structural_violations(rejected)
    assert len(violations) == 4


def test_campaign_reports_structural_and_timing_evidence_independently() -> None:
    """Fast clocks must not conceal structurally unbounded editor work."""

    scenario = PromptAbuseScenario(
        "structurally-heavy",
        "alpha",
        (PromptAbuseAction("key", value="right", expected_source="alpha"),),
        "alpha",
    )
    fast = summarize_latencies((1.0,))
    result = PromptAbuseScenarioResult(
        scenario=scenario,
        repetition=0,
        dispatch_samples=(),
        latency=fast,
        burst_dispatch_ms=1.0,
        settle_ms=0.0,
        actual_text_on_mismatch=None,
        projection_current=True,
        semantic_current=True,
        invariant_violations=(),
        deep_trace_enabled=False,
        structural_violations=("structural_budget:test",),
    )
    report = PromptAbuseCampaignReport(
        revision="test",
        qt_platform="offscreen",
        seed=7,
        frame_budget_ms=16.667,
        results=(result,),
    )

    assert not report.structural_performance_passed
    assert report.timing_target_passed
    assert "structural_violations=('structural_budget:test',)" in format_summary(report)


def test_structural_instrumentation_attributes_external_counts_per_action() -> None:
    """Opt-in method instrumentation should remain attributable by action."""

    probe = PromptAbuseActionCounterProbe(object())
    with prompt_abuse_structural_instrumentation(enabled=True) as instrumentation:
        assert instrumentation is not None
        probe.begin_unit()
        instrumentation.projection_rebuild.record(2.0)
        instrumentation.layout_snapshot.record(3.0)
        delta = probe.finish_unit(action_index=4, unit_index=0, label="type:'x'")

    assert dict(delta.counter_deltas) == {
        "instrumented_layout_snapshot_count": 1.0,
        "instrumented_projection_rebuild_count": 1.0,
    }


def test_structural_campaign_marks_clock_evidence_as_instrumented(
    tmp_path: Path,
) -> None:
    """Structural runs must never masquerade as reference timing evidence."""

    scenario = PromptAbuseScenario(
        "fake",
        "alpha",
        (PromptAbuseAction("key", value="right", expected_source="alpha"),),
        "alpha",
    )

    def fake_runner(
        run_scenario: PromptAbuseScenario,
        *,
        repetition: int,
        artifact_root: Path,
        deep_trace: bool,
    ) -> PromptAbuseScenarioResult:
        """Return a correct empty result inside the instrumented campaign."""

        _ = (repetition, artifact_root, deep_trace)
        return PromptAbuseScenarioResult(
            scenario=run_scenario,
            repetition=0,
            dispatch_samples=(),
            latency=summarize_latencies(()),
            burst_dispatch_ms=0.0,
            settle_ms=0.0,
            actual_text_on_mismatch=None,
            projection_current=True,
            semantic_current=True,
            invariant_violations=(),
            deep_trace_enabled=False,
        )

    report = run_campaign(
        (scenario,),
        repetitions=1,
        seed=7,
        frame_budget_ms=16.667,
        artifact_root=tmp_path,
        structural_probe=True,
        scenario_runner=fake_runner,
        platform_name=lambda: "offscreen-test",
    )

    assert report.structural_probe_enabled
    assert not report.timing_evidence_representative
    assert "timing_confidence=instrumented" in format_summary(report)


def test_hostile_workloads_cover_typing_edits_lifecycle_and_layout_pressure() -> None:
    """The deterministic matrix should attack more than ordinary key insertion."""

    scenarios = hostile_prompt_scenarios()
    by_name = {scenario.name: scenario for scenario in scenarios}

    assert by_name["empty-key-slam"].actions[0].value == KEY_SLAM
    assert by_name["long-decorated-start"].cursor_position == 0
    middle = by_name["long-decorated-middle"]
    assert middle.cursor_position == len(middle.initial_text) // 2
    end = by_name["long-decorated-end"]
    assert end.cursor_position == len(end.initial_text)
    assert len(end.initial_text) >= 8_000
    assert {
        "mixed-destructive-editing",
        "paste-undo-redo",
        "scene-marker-creation",
        "selection-replace-delete",
        "resize-wrap-churn",
        "autocomplete-race-churn",
        "seeded-mixed-abuse",
        "lifecycle-scroll-switch-churn",
        "region-separator-horizontal-atomic-navigation",
        "region-separator-vertical-navigation",
        "region-separator-mouse-placement",
        "region-separator-raw-rich-boundary",
        "region-separator-topology-promotion",
        "region-separator-adjacent-authoring",
        "region-separator-adjacent-partition-population",
        "region-separator-continued-authoring",
        "region-separator-nearby-authoring",
        "region-separator-delete-join-split",
        "region-separator-paste-selection-resize",
        "region-separator-multi-line-break",
        "region-separator-seeded-churn",
        "region-separator-canvas-lifecycle",
        "regional-separator-cross-partition-drag",
        "regional-separator-repeated-cross-partition-drag",
        "regional-separator-all-target-sweep",
        "regional-separator-all-source-sweep",
        "regional-separator-mixed-boundary-sweep",
        "regional-separator-leading-partition-exit",
        "regional-separator-trailing-partition-exit",
        "regional-separator-multi-partition-drag",
        "wildcard-txt-zebra-typing",
        "wildcard-scene-marker-error",
        "wildcard-csv-quoted-typing",
        "wildcard-mouse-drag-zebra",
        "prompt-viewport-repaint",
        "wildcard-viewport-repaint",
        "prompt-long-decorated-repaint",
    }.issubset(by_name)
    action_kinds = {
        action.kind for scenario in scenarios for action in scenario.actions
    }
    assert {
        "type",
        "paste",
        "key",
        "select",
        "resize",
        "scroll",
        "focus_cycle",
        "workflow_round_trip",
        "canvas_round_trip",
        "reorder_drag_press",
        "reorder_drag_threshold",
        "reorder_drag_move",
        "reorder_drag_release",
        "request_paint",
        "event_turn",
        "drain_events",
    } <= action_kinds
    assert by_name["wildcard-txt-zebra-typing"].editor_kind == "wildcard_txt"
    assert by_name["wildcard-csv-quoted-typing"].editor_kind == "wildcard_csv"
    seeded = by_name["seeded-mixed-abuse"]
    assert seeded.seed == 7
    assert len(seeded.actions) >= 48
    assert {"type", "paste", "select", "resize", "drain_events"} <= {
        action.kind for action in seeded.actions
    }
    separator_seeded = by_name["region-separator-seeded-churn"]
    assert separator_seeded.seed == 7
    assert len(separator_seeded.actions) >= 32
    assert {
        "key",
        "mouse_caret",
        "mouse_drag_selection",
        "display_mode",
        "resize",
        "request_paint",
        "drain_events",
    } <= {action.kind for action in separator_seeded.actions}
    search = by_name["search-highlight-scroll-paint"]
    search_ranges = next(
        action.source_ranges
        for action in search.actions
        if action.kind == "search_highlights" and action.value == "set"
    )
    assert len(search_ranges) >= 36
    assert {length for _start, length in search_ranges} == {len("masterpiece")}


def test_operation_coverage_requires_every_editor_feature() -> None:
    """The hostile matrix must retain complete prompt-editor operation coverage."""

    coverage = capture_operation_coverage(hostile_prompt_scenarios())

    assert "text.type" in coverage.covered
    assert "reorder.pointer_move" in coverage.covered
    assert "autocomplete.accept" in coverage.covered
    assert "diagnostic.context_menu" in coverage.covered
    assert "diagnostic.action" in coverage.covered
    assert "reorder.pointer_cancel" in coverage.covered
    assert coverage.missing == ()


def test_latency_summary_uses_nearest_rank_percentiles() -> None:
    """Latency summaries should preserve tail spikes for assistant ranking."""

    values = tuple(float(index) for index in range(1, 101))

    summary = summarize_latencies(values)

    assert summary == PromptAbuseLatencySummary(
        p50_ms=50.0,
        p95_ms=95.0,
        p99_ms=99.0,
        maximum_ms=100.0,
    )
    assert percentile((), 95) == 0.0


def test_timing_target_rejects_slow_non_typing_operations() -> None:
    """The reference target must include interaction and queued-work stalls."""

    scenario = PromptAbuseScenario(
        "interaction-only",
        "alpha",
        (PromptAbuseAction("key_press", value="alt", expected_source="alpha"),),
        "alpha",
    )
    zero = summarize_latencies(())
    slow = summarize_latencies((28.0, 35.0, 42.0))
    result = PromptAbuseScenarioResult(
        scenario=scenario,
        repetition=0,
        dispatch_samples=(
            PromptAbuseDispatchSample(
                0,
                0,
                "key_press:'alt'",
                35.0,
                True,
                True,
                latency_class="interaction",
            ),
        ),
        latency=slow,
        burst_dispatch_ms=35.0,
        settle_ms=0.0,
        actual_text_on_mismatch=None,
        projection_current=True,
        semantic_current=True,
        invariant_violations=(),
        deep_trace_enabled=False,
        latency_breakdown=PromptAbuseLatencyBreakdown(
            text_input=zero,
            interaction=slow,
            lifecycle=zero,
            backlog_drain=zero,
            text_input_count=0,
            interaction_count=3,
            lifecycle_count=0,
            backlog_drain_count=0,
        ),
    )

    report = PromptAbuseCampaignReport(
        revision="test",
        qt_platform="offscreen",
        seed=7,
        frame_budget_ms=16.667,
        results=(result,),
    )

    assert not report.timing_target_passed


def test_timing_target_rejects_tail_spikes_hidden_by_p95() -> None:
    """A nominal p95 must not hide visible p99 or maximum frame stalls."""

    scenario = PromptAbuseScenario(
        "tail-spike",
        "alpha",
        (PromptAbuseAction("key", value="right", expected_source="alpha"),),
        "alpha",
    )
    timings = tuple(4.0 for _index in range(99)) + (80.0,)
    latency = summarize_latencies(timings)
    zero = summarize_latencies(())
    result = PromptAbuseScenarioResult(
        scenario=scenario,
        repetition=0,
        dispatch_samples=(),
        latency=latency,
        burst_dispatch_ms=sum(timings),
        settle_ms=0.0,
        actual_text_on_mismatch=None,
        projection_current=True,
        semantic_current=True,
        invariant_violations=(),
        deep_trace_enabled=False,
        latency_breakdown=PromptAbuseLatencyBreakdown(
            text_input=latency,
            interaction=zero,
            lifecycle=zero,
            backlog_drain=zero,
            text_input_count=len(timings),
            interaction_count=0,
            lifecycle_count=0,
            backlog_drain_count=0,
        ),
    )
    report = PromptAbuseCampaignReport(
        revision="test",
        qt_platform="offscreen",
        seed=7,
        frame_budget_ms=16.667,
        results=(result,),
    )

    assert latency.p95_ms == 4.0
    assert not report.timing_target_passed


def test_campaign_report_marks_externally_contended_timing_environment() -> None:
    """Assistant summaries should distinguish editor cost from competing CPU work."""

    report = PromptAbuseCampaignReport(
        revision="test",
        qt_platform="offscreen",
        seed=7,
        frame_budget_ms=16.667,
        results=(),
        system_load=PromptAbuseSystemLoad(
            elapsed_seconds=5.0,
            logical_cpu_count=32,
            system_cpu_percent=62.0,
            harness_cpu_percent=3.0,
            competing_cpu_percent=59.0,
        ),
    )

    summary = format_summary(report)

    assert report.system_load is not None
    assert report.system_load.contended
    assert not report.timing_evidence_representative
    assert "competing=59.0%" in summary
    assert "timing_confidence=contended" in summary


def test_campaign_report_does_not_claim_unmeasured_timing_is_representative() -> None:
    """Missing load evidence must remain explicit in assistant summaries."""

    report = PromptAbuseCampaignReport(
        revision="test",
        qt_platform="offscreen",
        seed=7,
        frame_budget_ms=16.667,
        results=(),
    )

    assert not report.timing_evidence_representative
    assert "timing_confidence=unmeasured" in format_summary(report)


def test_minimizer_truncates_one_typed_action_at_the_selected_unit() -> None:
    """A slow character should become the final unit of an exact replay."""

    scenario = PromptAbuseScenario(
        "typing",
        "alpha",
        (
            PromptAbuseAction(
                "type",
                value="abcdef",
                expected_source="alphaabcdef",
                expected_cursor_position=11,
            ),
        ),
        "alphaabcdef",
        cursor_position=5,
    )

    minimized = truncate_scenario_to_sample(
        scenario,
        action_index=0,
        unit_index=2,
    )

    assert minimized.actions[0].value == "abc"
    assert minimized.expected_text == "alphaabc"
    assert minimized.actions[0].expected_cursor_position == 8


def test_campaign_repeats_scenarios_and_writes_assistant_readable_report(
    tmp_path: Path,
) -> None:
    """Campaign orchestration should retain raw samples and reproducible inputs."""

    scenario = PromptAbuseScenario(
        "fake",
        "alpha",
        (
            PromptAbuseAction(
                "type",
                value=" xy",
                expected_source="alpha xy",
                expected_cursor_position=8,
            ),
        ),
        "alpha xy",
        cursor_position=5,
    )
    calls: list[tuple[str, int, bool]] = []

    def fake_runner(
        run_scenario: PromptAbuseScenario,
        *,
        repetition: int,
        artifact_root: Path,
        deep_trace: bool,
    ) -> PromptAbuseScenarioResult:
        """Return deterministic evidence while recording orchestration inputs."""

        assert artifact_root == tmp_path
        calls.append((run_scenario.name, repetition, deep_trace))
        samples = (
            PromptAbuseDispatchSample(0, 0, "type:' '", 2.0 + repetition, True, True),
            PromptAbuseDispatchSample(0, 1, "type:'x'", 4.0 + repetition, True, True),
            PromptAbuseDispatchSample(0, 2, "type:'y'", 8.0 + repetition, True, True),
        )
        return PromptAbuseScenarioResult(
            scenario=run_scenario,
            repetition=repetition,
            dispatch_samples=samples,
            latency=summarize_latencies(
                tuple(sample.dispatch_ms for sample in samples)
            ),
            burst_dispatch_ms=14.0,
            settle_ms=1.0,
            actual_text_on_mismatch=None,
            projection_current=True,
            semantic_current=True,
            invariant_violations=(),
            deep_trace_enabled=deep_trace,
        )

    report = run_campaign(
        (scenario,),
        repetitions=2,
        seed=41,
        frame_budget_ms=16.667,
        artifact_root=tmp_path,
        deep_trace=False,
        scenario_runner=fake_runner,
        platform_name=lambda: "offscreen-test",
    )
    report_path = tmp_path / "report.json"
    write_report(report, report_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert calls == [("fake", 0, False), ("fake", 1, False)]
    assert report.correctness_passed
    assert report.structural_performance_passed
    assert report.timing_target_passed
    assert payload["seed"] == 41
    assert payload["results"][0]["scenario"]["actions"][0]["value"] == " xy"
    assert "p95=" in format_summary(report)

    loaded = load_report_scenarios(report_path, scenario_name="fake")
    assert loaded == (scenario,)
    prefix = scenario_prefix(loaded[0], action_count=1)
    assert prefix.expected_text == "alpha xy"
    assert prefix.name == "fake-actions-1"

    comparison = compare_report_files(report_path, report_path)
    assert not comparison.correctness_regressed
    assert comparison.scenarios[0].p95.delta_ms == 0.0
    assert "fake" in format_comparison(comparison)
