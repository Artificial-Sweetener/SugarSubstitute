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

"""Verify prompt reorder activation and commit instrumentation contracts."""

from __future__ import annotations

from typing import Any, cast


from PySide6.QtCore import QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.overlays import (
    PromptReorderView,
    SegmentReorderOverlay,
)


from .support import (
    _assert_plain_alt_keeps_surface_text_ownership,
    _counter_delta,
    _create_prompt_editor,
    _ensure_qapp,
    _flush_preview_sync,
    _open_reorder_overlay,
    _overlay_chip_by_segment_index,
    _performance_counters,
    _process_events,
)


def test_plain_alt_leaves_text_and_raster_work_on_projection_surface(
    widgets: list[QWidget],
) -> None:
    """Alt activation should add chrome without duplicating projection text."""

    app = _ensure_qapp()
    box = _create_prompt_editor(
        widgets,
        text=", ".join(f"tag_{index}" for index in range(48)),
    )

    QTest.keyPress(box, Qt.Key.Key_Alt)

    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    immediate = _performance_counters(overlay)
    view = overlay.findChild(PromptReorderView, "segmentReorderView")
    assert view is not None
    assert immediate["raster_build_count"] == 0
    assert immediate["preview_geometry_full_count"] == 1
    assert view.render_state.live_chips == ()
    surface_chrome = cast(
        Any, overlay
    )._editor._surface._reorder_surface_visual_state.state.chrome_snapshot
    assert surface_chrome is not None
    assert surface_chrome.chips
    assert view.render_state.raster_paint_count == 0

    _process_events(app)

    settled = _performance_counters(overlay)
    assert settled["raster_build_count"] == 0
    _assert_plain_alt_keeps_surface_text_ownership(overlay)
    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_pointer_release_does_not_mutate_source_or_undo(
    widgets: list[QWidget],
) -> None:
    """Drag start should do setup once and release should not mutate source."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha,beta,")
    cursor = box.textCursor()
    cursor.setPosition(7)
    box.setTextCursor(cursor)
    can_undo_before = box.canUndo()

    overlay = _open_reorder_overlay(box)
    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    target_global = first_chip.leading_global_point()

    QTest.mousePress(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    _process_events(app)

    before_drag_start = _performance_counters(overlay)

    QTest.mouseMove(second_chip.overlay, second_chip.mapFromGlobal(target_global), 10)
    _flush_preview_sync(box)

    after_drag_start = _performance_counters(overlay)
    assert (
        _counter_delta(
            before_drag_start,
            after_drag_start,
            "drag_proxy_render_state_rebuild_count",
        )
        == 0
    )
    assert (
        _counter_delta(
            before_drag_start,
            after_drag_start,
            "drag_proxy_render_state_reuse_count",
        )
        == 1
    )
    assert after_drag_start["drag_proxy_render_state_invalidation_count"] == 0
    assert _counter_delta(before_drag_start, after_drag_start, "drag_move_count") == 0
    assert (
        _counter_delta(
            before_drag_start,
            after_drag_start,
            "pointer_unexpected_work_count",
        )
        == 0
    )
    assert (
        _counter_delta(
            before_drag_start,
            after_drag_start,
            "projection_snapshot_rebuild_count",
        )
        <= 3
    )
    assert after_drag_start["max_drag_move_ms"] == 0.0
    before_release = after_drag_start

    QTest.mouseRelease(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.mapFromGlobal(target_global),
        delay=10,
    )
    _process_events(app)

    assert box.toPlainText() == "alpha,beta,"
    assert box.canUndo() is can_undo_before
    assert overlay._render_publication.publication.unsafe_transient_indices == ()
    after_release = _performance_counters(overlay)
    assert (
        after_release["drag_proxy_render_state_rebuild_count"]
        == before_release["drag_proxy_render_state_rebuild_count"]
    )
    assert (
        after_release["drag_proxy_render_state_invalidation_count"]
        == before_release["drag_proxy_render_state_invalidation_count"]
    )
    assert (
        _counter_delta(
            before_release,
            after_release,
            "projection_snapshot_rebuild_count",
        )
        <= 1
    )


def test_plain_alt_keeps_surface_text_after_theme_or_font_invalidation(
    widgets: list[QWidget],
) -> None:
    """Theme churn should not transfer plain-Alt text into the overlay."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")

    overlay = _open_reorder_overlay(box)
    QApplication.sendEvent(overlay, QEvent(QEvent.Type.FontChange))
    _process_events(app)

    _assert_plain_alt_keeps_surface_text_ownership(overlay)
    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)
    assert getattr(box, "_segment_overlay") is None

    reopened_overlay = _open_reorder_overlay(box)
    _assert_plain_alt_keeps_surface_text_ownership(reopened_overlay)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_geometry_refresh_preserves_complete_animation_paint_ownership(
    widgets: list[QWidget],
) -> None:
    """A resize during displacement must not leave translated chrome without text."""

    app = _ensure_qapp()
    box = _create_prompt_editor(
        widgets,
        width=520,
        height=260,
        text=", ".join(f"tag_{index}" for index in range(72)),
    )
    cursor = box.textCursor()
    cursor.setPosition(2)
    box.setTextCursor(cursor)
    overlay = _open_reorder_overlay(box)
    animation_owner = cast(Any, overlay)._animation_presentation
    animation_owner.set_duration_ms(1000)

    QTest.keyClick(box, Qt.Key.Key_Right)
    _process_events(app)
    assert animation_owner.publication.displacement_rects_by_index

    host = widgets[0]
    host.resize(host.width() + 24, host.height() + 16)
    _process_events(app)

    state = cast(Any, overlay)._view.render_state
    active_chips = state.preview_chips if state.preview_active else state.live_chips
    surface_chrome = cast(
        Any, box
    )._surface._reorder_surface_visual_state.state.chrome_snapshot
    surface_indices = (
        set()
        if surface_chrome is None
        else {chip.segment_index for chip in surface_chrome.chips}
    )
    rendered_indices = surface_indices | {chip.segment_index for chip in active_chips}
    expected_indices = set(cast(Any, overlay)._preview_visual_owner.visuals_by_index)

    assert rendered_indices == expected_indices
    assert not animation_owner.publication.displacement_rects_by_index

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)
