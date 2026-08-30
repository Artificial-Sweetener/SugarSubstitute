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

"""Verify prompt reorder invalidation instrumentation contracts."""

from __future__ import annotations

from typing import Any, cast


from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget


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


def test_reorder_drag_proxy_font_invalidation_rebuilds_before_visible_use(
    widgets: list[QWidget],
) -> None:
    """Explicit proxy invalidation should rebuild once, then reuse while moving."""

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
    target_global = first_chip.leading_global_point()

    QTest.mousePress(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    QTest.mouseMove(second_chip.overlay, second_chip.mapFromGlobal(target_global), 10)
    _process_events(app)
    before = _performance_counters(overlay)

    changed_font = QFont(editor.viewport().font())
    changed_font.setPointSize(changed_font.pointSize() + 2)
    editor.viewport().setFont(changed_font)
    app.sendEvent(overlay, QEvent(QEvent.Type.FontChange))
    _flush_preview_sync(editor)

    after = _performance_counters(overlay)
    assert (
        _counter_delta(
            before,
            after,
            "drag_proxy_render_state_invalidation_count",
        )
        == 1
    )
    assert (
        _counter_delta(
            before,
            after,
            "drag_proxy_render_state_rebuild_count",
        )
        == 1
    )

    QTest.mouseMove(
        second_chip.overlay,
        second_chip.mapFromGlobal(target_global + QPoint(3, 0)),
        10,
    )
    _process_events(app)
    after_move = _performance_counters(overlay)
    assert (
        _counter_delta(
            after,
            after_move,
            "drag_proxy_render_state_rebuild_count",
        )
        == 0
    )
    assert _counter_delta(after, after_move, "projection_snapshot_rebuild_count") == 0
    assert _counter_delta(after, after_move, "animation_plan_build_count") == 0
    _assert_timing_observed(after_move, "max_drag_move_ms")

    QTest.mouseRelease(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(target_global),
        delay=10,
    )
    _process_events(app)


def test_reorder_autoscroll_steps_do_not_rebuild_surface_projection(
    widgets: list[QWidget],
) -> None:
    """Autoscroll ticks should coalesce geometry/projection work behind counters."""

    app = _ensure_qapp()
    editor = _create_prompt_editor(
        widgets,
        width=240,
        height=120,
        text=", ".join(
            f"segment {index} with a longer description" for index in range(20)
        ),
    )
    overlay = _open_reorder_overlay(editor)
    scrollbar = editor.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(0)
    _process_events(app)

    dragged_chip = _overlay_chip_by_segment_index(overlay, 0)
    edge_global = overlay.mapToGlobal(
        QPoint(overlay.width() // 2, overlay.height() - 2)
    )
    QTest.mousePress(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    threshold_position = QPoint(
        dragged_chip.rect().center().x() + QApplication.startDragDistance() + 1,
        dragged_chip.rect().center().y(),
    )
    QTest.mouseMove(dragged_chip.overlay, threshold_position, 10)
    QTest.mouseMove(dragged_chip.overlay, dragged_chip.mapFromGlobal(edge_global), 10)
    _flush_preview_sync(editor)

    before = _performance_counters(overlay)

    before_geometry_generation = overlay.geometry_generation_state().generation_id
    cast(Any, overlay)._autoscroll.apply_step_for_tests()
    cast(Any, overlay)._autoscroll.apply_step_for_tests()

    after_ticks_before_flush = _performance_counters(overlay)

    assert (
        _counter_delta(
            before,
            after_ticks_before_flush,
            "autoscroll_invalidation_count",
        )
        >= 2
    )
    assert (
        _counter_delta(
            before,
            after_ticks_before_flush,
            "autoscroll_coalesced_count",
        )
        >= 1
    )
    assert after_ticks_before_flush["autoscroll_pending_invalidation_count"] == 1
    assert (
        _counter_delta(
            before,
            after_ticks_before_flush,
            "projection_snapshot_rebuild_count",
        )
        == 0
    )

    assert (
        _counter_delta(
            before,
            after_ticks_before_flush,
            "animation_plan_build_count",
        )
        == 0
    )
    assert (
        _counter_delta(
            before,
            after_ticks_before_flush,
            "preview_scheduler_request_count",
        )
        >= 1
    )

    QTest.mouseRelease(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(edge_global),
        delay=10,
    )
    _process_events(app)

    after_release = _performance_counters(overlay)

    invalidation_delta = _counter_delta(
        before,
        after_release,
        "autoscroll_invalidation_count",
    )
    flush_delta = _counter_delta(before, after_release, "autoscroll_flush_count")
    projection_rebuild_delta = _counter_delta(
        before,
        after_release,
        "projection_snapshot_rebuild_count",
    )
    assert invalidation_delta >= 2
    assert flush_delta == 1
    assert projection_rebuild_delta < invalidation_delta
    _assert_timing_observed(after_release, "max_drag_move_ms")
    assert after_release["autoscroll_pending_invalidation_count"] == 0
    assert (
        overlay.geometry_generation_state().generation_id > before_geometry_generation
    )
    resolution_delta = _counter_delta(
        before,
        after_release,
        "drop_target_no_change_count",
    ) + _counter_delta(
        before,
        after_release,
        "drop_target_changed_count",
    )
    assert resolution_delta >= 1
