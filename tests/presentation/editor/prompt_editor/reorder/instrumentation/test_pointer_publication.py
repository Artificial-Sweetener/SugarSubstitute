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

"""Verify prompt reorder pointer publication instrumentation contracts."""

from __future__ import annotations

from typing import Any, cast

import pytest


from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.projection.reorder_animation import (
    PromptReorderAnimationTarget,
)


from .support import (
    _assert_timing_observed,
    _counter_delta,
    _create_prompt_editor,
    _editor_reorder_preview_text,
    _ensure_qapp,
    _flush_preview_sync,
    _open_reorder_overlay,
    _overlay_chip_by_segment_index,
    _painted_preview_rect,
    _performance_counters,
    _process_events,
)


def test_reorder_target_change_paints_displaced_neighbors_after_preview_sync(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pointer target changes should visibly displace neighbors in the paint state."""

    app = _ensure_qapp()
    editor = _create_prompt_editor(
        widgets,
        width=420,
        height=220,
        text="alpha,beta,gamma,",
    )
    overlay = _open_reorder_overlay(editor)
    animation_owner = cast(Any, overlay)._animation_presentation
    animation_owner.set_duration_ms(1000)
    recorded_plans: list[Any] = []
    original_apply_plan = animation_owner.apply_plan

    def record_apply_plan(plan: Any, **context: Any) -> None:
        """Record pointer displacement plans while preserving presenter behavior."""

        recorded_plans.append(plan)
        original_apply_plan(plan, **context)

    monkeypatch.setattr(animation_owner, "apply_plan", record_apply_plan)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    first_target = first_chip.leading_global_point()

    QTest.mousePress(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    _process_events(app)

    before = _performance_counters(overlay)
    threshold_position = QPoint(
        second_chip.rect().center().x() - (QApplication.startDragDistance() + 1),
        second_chip.rect().center().y(),
    )
    QTest.mouseMove(second_chip.overlay, threshold_position, 10)
    movement_before = _performance_counters(overlay)
    QTest.mouseMove(second_chip.overlay, second_chip.mapFromGlobal(first_target), 10)
    immediate_after = _performance_counters(overlay)

    assert editor.toPlainText() == "alpha,beta,gamma,"
    assert _counter_delta(movement_before, immediate_after, "drag_move_count") == 1
    assert (
        _counter_delta(
            movement_before,
            immediate_after,
            "drop_target_changed_count",
        )
        == 1
    )

    _flush_preview_sync(editor)
    after_sync = _performance_counters(overlay)

    assert _counter_delta(before, after_sync, "animation_plan_build_count") >= 1
    assert _counter_delta(before, after_sync, "animation_plan_applied_count") >= 1
    assert overlay.preview_rect_for_segment(1) is not None
    assert recorded_plans
    displaced_target = cast(
        PromptReorderAnimationTarget,
        recorded_plans[-1].changed_targets[0],
    )
    painted_rect = _painted_preview_rect(overlay, displaced_target.segment_index)
    assert painted_rect != displaced_target.target_rect
    start_left = displaced_target.start_rect.left()
    painted_left = painted_rect.left()
    target_left = displaced_target.target_rect.left()
    assert start_left <= painted_left
    assert painted_left < target_left
    assert overlay.preview_rect_for_segment(displaced_target.segment_index) == (
        displaced_target.target_rect.toAlignedRect()
    )

    QTest.mouseRelease(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(first_target),
        delay=10,
    )
    _process_events(app)


def test_reorder_rapid_target_changes_coalesce_one_preview_sync(
    widgets: list[QWidget],
) -> None:
    """Changed-target work should coalesce to one plan per event-loop turn."""

    app = _ensure_qapp()
    editor = _create_prompt_editor(
        widgets,
        width=460,
        height=220,
        text="alpha,beta,gamma,delta,",
    )
    overlay = _open_reorder_overlay(editor)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    third_chip = _overlay_chip_by_segment_index(overlay, 2)
    first_target = first_chip.leading_global_point()
    third_target = third_chip.trailing_global_point()
    second_target = second_chip.trailing_global_point()

    QTest.mousePress(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    QTest.mouseMove(second_chip.overlay, second_chip.mapFromGlobal(first_target), 10)
    _process_events(app)

    cast(Any, overlay)._instrumentation_max_drag_move_ms = 0.0
    before = _performance_counters(overlay)
    QTest.mouseMove(second_chip.overlay, second_chip.mapFromGlobal(second_target), 10)
    QTest.mouseMove(second_chip.overlay, second_chip.mapFromGlobal(third_target), 10)
    immediate_after = _performance_counters(overlay)

    assert _counter_delta(before, immediate_after, "drop_target_changed_count") == 2
    assert (
        _counter_delta(before, immediate_after, "preview_scheduler_request_count") == 2
    )
    assert _counter_delta(before, immediate_after, "preview_scheduler_run_count") == 0
    assert _counter_delta(before, immediate_after, "preview_geometry_full_count") == 0
    assert (
        _counter_delta(before, immediate_after, "projection_snapshot_rebuild_count")
        == 0
    )
    assert _counter_delta(before, immediate_after, "animation_plan_build_count") == 0
    assert _counter_delta(before, immediate_after, "pointer_unexpected_work_count") == 0

    _flush_preview_sync(editor)
    after_sync = _performance_counters(overlay)

    assert _counter_delta(before, after_sync, "preview_scheduler_run_count") == 1
    assert _counter_delta(before, after_sync, "preview_geometry_full_count") == 1
    assert _counter_delta(before, after_sync, "animation_plan_build_count") == 1
    assert _counter_delta(before, after_sync, "animation_plan_applied_count") == 1
    _assert_timing_observed(after_sync, "max_drag_move_ms")
    _assert_timing_observed(after_sync, "max_preview_sync_ms")
    assert editor.toPlainText() == "alpha,beta,gamma,delta,"
    assert overlay.preview_rect_for_segment(1) is not None

    before_position_notification = _performance_counters(overlay)
    overlay.refresh_geometry(reason="test_position_notification")
    after_position_notification = _performance_counters(overlay)
    assert (
        _counter_delta(
            before_position_notification,
            after_position_notification,
            "preview_geometry_full_count",
        )
        == 0
    )

    QTest.mouseRelease(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(third_target),
        delay=10,
    )
    _process_events(app)


def test_reorder_wrapped_drag_preview_builds_wrapped_animation_plan(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapped target changes should animate toward settled wrapped rects."""

    app = _ensure_qapp()
    editor = _create_prompt_editor(
        widgets,
        width=170,
        height=180,
        text="alpha, beta, gamma, delta",
    )
    overlay = _open_reorder_overlay(editor)
    dragged_chip = _overlay_chip_by_segment_index(overlay, 3)
    target_chip = _overlay_chip_by_segment_index(overlay, 1)
    recorded_plans: list[Any] = []
    animation_owner = cast(Any, overlay)._animation_presentation
    original_apply_plan = animation_owner.apply_plan

    def record_apply_plan(plan: Any, **context: Any) -> None:
        """Record integration plans while preserving presenter behavior."""

        recorded_plans.append(plan)
        original_apply_plan(plan, **context)

    monkeypatch.setattr(animation_owner, "apply_plan", record_apply_plan)
    target_global = target_chip.leading_global_point()

    QTest.mousePress(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip.overlay, dragged_chip.mapFromGlobal(target_global), 10)
    immediate_after = _performance_counters(overlay)

    assert immediate_after["animation_plan_build_count"] == 0

    _flush_preview_sync(editor)
    after_sync = _performance_counters(overlay)

    assert overlay.ordered_chip_indices() == [0, 3, 1, 2]
    assert _editor_reorder_preview_text(editor) == "alpha, delta, beta, gamma"
    assert after_sync["animation_plan_build_count"] == 1
    assert recorded_plans
    changed_targets = recorded_plans[-1].changed_targets
    assert changed_targets
    for target in changed_targets:
        preview_rect_value = overlay.preview_rect_for_segment(target.segment_index)
        assert preview_rect_value is not None
        preview_rect = QRectF(preview_rect_value)
        assert target.target_rect.left() == preview_rect.left()
        assert target.target_rect.top() == preview_rect.top()
        assert target.target_rect.width() == preview_rect.width()

    QTest.mouseRelease(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(target_global),
        delay=10,
    )
    _process_events(app)

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    _process_events(app)

    assert editor.toPlainText() == "alpha, delta, beta, gamma"
