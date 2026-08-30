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

"""Verify prompt reorder pointer instrumentation instrumentation contracts."""

from __future__ import annotations

from typing import Any, cast

import pytest


from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget


from .support import (
    _assert_timing_observed,
    _counter_delta,
    _create_prompt_editor,
    _ensure_qapp,
    _flush_preview_sync,
    _open_reorder_overlay,
    _overlay_chip_by_segment_index,
    _performance_counters,
    _process_events,
)


def test_reorder_unchanged_target_pointer_move_preserves_hot_path_counters(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unchanged-target pointer moves prove the cheap path with counters.

    GUI timing budgets are intentionally observed through `max_drag_move_ms`;
    deterministic CI assertions use owner counters because Qt/offscreen timing
    varies by host load.
    """

    app = _ensure_qapp()
    box = _create_prompt_editor(
        widgets,
        width=420,
        height=220,
        text="alpha,beta,",
    )
    overlay = _open_reorder_overlay(box)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    target_global = first_chip.leading_global_point()

    QTest.mousePress(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    QTest.mouseMove(second_chip.overlay, second_chip.mapFromGlobal(target_global), 10)
    _flush_preview_sync(box)

    cast(Any, overlay)._instrumentation_max_drag_move_ms = 0.0
    before = _performance_counters(overlay)
    before_pointer_state = overlay.pointer_reorder_state()
    before_animation_state = overlay.animation_generation_state()
    telemetry_type = type(cast(Any, overlay)._telemetry)

    with monkeypatch.context() as telemetry_patch:
        assert not hasattr(
            cast(Any, overlay)._geometry,
            "resolve_drop_target_for_drag_rect",
        )

        def reject_heavy_context(
            *_args: object,
            **_kwargs: object,
        ) -> dict[str, object]:
            """Fail if unchanged-target movement builds structural diagnostics."""

            raise AssertionError("unchanged target built heavy telemetry context")

        for helper_name in (
            "style_context",
            "visual_context",
            "held_shadow_context",
            "target_visual_context",
            "visual_delta_context",
        ):
            telemetry_patch.setattr(
                telemetry_type,
                helper_name,
                reject_heavy_context,
            )

        QTest.mouseMove(
            second_chip.overlay,
            second_chip.mapFromGlobal(target_global + QPoint(1, 0)),
            10,
        )
        _process_events(app)

        after = _performance_counters(overlay)
        after_pointer_state = overlay.pointer_reorder_state()
        after_animation_state = overlay.animation_generation_state()

        assert _counter_delta(before, after, "drag_move_count") == 1
        _assert_timing_observed(after, "max_drag_move_ms")
        assert _counter_delta(before, after, "drop_target_no_change_count") == 1
        assert (
            after_pointer_state.active_drop_target
            == before_pointer_state.active_drop_target
        )
        assert (
            after_animation_state.generation_id == before_animation_state.generation_id
        )
        for counter_name in (
            "projection_snapshot_rebuild_count",
            "preview_scheduler_request_count",
            "preview_scheduler_run_count",
            "preview_geometry_full_count",
            "drag_proxy_render_state_rebuild_count",
            "drag_proxy_render_state_invalidation_count",
            "autoscroll_invalidation_count",
            "animation_plan_build_count",
            "animation_plan_applied_count",
            "pointer_preview_rebuild_count",
            "pointer_full_refresh_count",
            "pointer_base_cache_miss_count",
            "pointer_paint_request_count",
            "pointer_unexpected_work_count",
        ):
            assert after[counter_name] == before[counter_name]

        def sample_target_changes_only(
            _self: object,
            *,
            move_count: int,
            target_changed: bool,
        ) -> bool:
            """Force the unchanged-target path to behave like an unsampled move."""

            _ = move_count
            return target_changed

        def reject_unsampled_timing(
            _self: object,
            event: str,
            *,
            started_at: float,
            **_context: object,
        ) -> float:
            """Fail if unchanged-target movement emits sampled timing telemetry."""

            _ = started_at
            raise AssertionError(f"unchanged target emitted timing telemetry: {event}")

        telemetry_patch.setattr(
            telemetry_type,
            "should_log_pointer_event",
            sample_target_changes_only,
        )
        telemetry_patch.setattr(telemetry_type, "log_timing", reject_unsampled_timing)

        QTest.mouseMove(
            second_chip.overlay,
            second_chip.mapFromGlobal(target_global + QPoint(2, 0)),
            10,
        )
        _process_events(app)

        unsampled_after = _performance_counters(overlay)
        assert _counter_delta(after, unsampled_after, "drag_move_count") == 1
        assert (
            _counter_delta(after, unsampled_after, "drop_target_no_change_count") == 1
        )

    QTest.mouseRelease(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(target_global),
        delay=10,
    )
    _process_events(app)


def test_reorder_target_change_pointer_move_records_rebuild_path_counters(
    widgets: list[QWidget],
) -> None:
    """Changed-target moves should schedule preview work without mutating source."""

    app = _ensure_qapp()
    editor = _create_prompt_editor(
        widgets,
        width=420,
        height=220,
        text="alpha,beta,gamma,",
    )
    overlay = _open_reorder_overlay(editor)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    third_chip = _overlay_chip_by_segment_index(overlay, 2)
    target_global = first_chip.leading_global_point()
    next_target_global = third_chip.trailing_global_point()

    QTest.mousePress(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    QTest.mouseMove(second_chip.overlay, second_chip.mapFromGlobal(target_global), 10)
    _process_events(app)
    cast(Any, overlay)._instrumentation_max_drag_move_ms = 0.0
    before = _performance_counters(overlay)

    QTest.mouseMove(
        second_chip.overlay,
        second_chip.mapFromGlobal(next_target_global),
        10,
    )
    _process_events(app)

    after = _performance_counters(overlay)
    pointer_state = overlay.pointer_reorder_state()
    preview_state = overlay.preview_target_state()
    geometry_state = overlay.geometry_generation_state()

    assert editor.toPlainText() == "alpha,beta,gamma,"
    assert _counter_delta(before, after, "drag_move_count") == 1
    assert _counter_delta(before, after, "drop_target_changed_count") == 1
    assert _counter_delta(before, after, "preview_scheduler_request_count") == 1
    assert _counter_delta(before, after, "preview_scheduler_run_count") == 0
    assert _counter_delta(before, after, "preview_geometry_full_count") == 0
    assert _counter_delta(before, after, "projection_snapshot_rebuild_count") == 0
    assert _counter_delta(before, after, "animation_plan_build_count") == 0
    assert _counter_delta(before, after, "pointer_unexpected_work_count") == 0
    _assert_timing_observed(after, "max_drag_move_ms")
    assert (
        _counter_delta(
            before,
            after,
            "drag_proxy_render_state_rebuild_count",
        )
        == 0
    )
    assert pointer_state.active_drop_target == preview_state.active_target
    assert geometry_state.prepared_geometry_identity.active_target == (
        pointer_state.active_drop_target
    )

    QTest.mouseRelease(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(target_global),
        delay=10,
    )
    _process_events(app)
