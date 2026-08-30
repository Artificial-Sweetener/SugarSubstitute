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

"""Verify prompt reorder keyboard animation plans instrumentation contracts."""

from __future__ import annotations

from typing import Any, cast

import pytest


from PySide6.QtCore import QRectF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.overlays import (
    SegmentReorderOverlay,
)


from .support import (
    _counter_delta,
    _create_prompt_editor,
    _editor_reorder_preview_text,
    _ensure_qapp,
    _performance_counters,
    _process_events,
)


def test_reorder_alt_left_builds_keyboard_animation_plan(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alt+Left should animate changed chips from settled keyboard preview geometry."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    animation_owner = cast(Any, overlay)._animation_presentation
    original_apply_plan = animation_owner.apply_plan
    recorded_plans: list[Any] = []
    before = _performance_counters(overlay)

    def record_apply_plan(plan: Any, **context: Any) -> None:
        """Record keyboard animation plans while preserving presenter behavior."""

        recorded_plans.append(plan)
        original_apply_plan(plan, **context)

    monkeypatch.setattr(animation_owner, "apply_plan", record_apply_plan)

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)
    after = _performance_counters(overlay)

    assert _editor_reorder_preview_text(box) == "beta, alpha, gamma"
    assert box.toPlainText() == "alpha, beta, gamma"
    assert _counter_delta(before, after, "animation_plan_build_count") == 1
    assert _counter_delta(before, after, "animation_plan_applied_count") == 1
    assert recorded_plans
    assert recorded_plans[-1].reason == "keyboard_target_changed"
    assert recorded_plans[-1].dragged_segment_index == 1
    assert overlay.preview_build_facts.snapshot().drop_target is not None
    assert all(
        target.segment_index != recorded_plans[-1].dragged_segment_index
        for target in recorded_plans[-1].changed_targets
    )
    assert recorded_plans[-1].changed_targets
    assert animation_owner.publication.displacement_rects_by_index

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_keyboard_animation_first_frame_is_coherent(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alt+Arrow should not publish a frame before the held-chip override exists."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    render_publication = cast(Any, overlay)._render_publication
    original_sync = render_publication.sync
    animation_frames: list[
        tuple[
            dict[int, QRectF],
            dict[int, QRectF],
            tuple[int, ...],
            tuple[int, ...],
        ]
    ] = []

    def record_animation_frame(*, reason: str) -> None:
        """Record frame override ownership while preserving real rendering."""

        original_sync(reason=reason)
        if reason == "animation_frame":
            publication = cast(Any, overlay)._animation_presentation.publication
            prepared = render_publication.publication
            overlay_state = prepared.overlay_state
            overlay_chips = (
                overlay_state.preview_chips
                if overlay_state.preview_active
                else overlay_state.live_chips
            )
            animation_frames.append(
                (
                    dict(publication.displacement_rects_by_index),
                    dict(publication.held_rects_by_index),
                    tuple(chip.segment_index for chip in prepared.surface.chips),
                    tuple(chip.segment_index for chip in overlay_chips),
                )
            )

    monkeypatch.setattr(
        render_publication,
        "sync",
        record_animation_frame,
    )

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)

    assert animation_frames
    first_frame = animation_frames[0]
    assert first_frame[0]
    assert set(first_frame[1]) == {1}
    assert 1 not in first_frame[2]
    assert 1 in first_frame[3]
    assert render_publication.publication.unsafe_transient_indices == ()

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_alt_right_captures_commit_snapshot_before_animation(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alt+Right should publish commit state before presenter animation runs."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(2)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    animation_owner = cast(Any, overlay)._animation_presentation
    original_apply_plan = animation_owner.apply_plan
    observed_orders: list[tuple[int, ...] | None] = []

    def record_snapshot_before_animation(plan: Any, **context: Any) -> None:
        """Record the public overlay snapshot when display animation is applied."""

        _ = plan
        latest_snapshot = overlay.commit_snapshot()
        observed_orders.append(
            None if latest_snapshot is None else latest_snapshot.ordered_chip_indices
        )
        original_apply_plan(plan, **context)

    monkeypatch.setattr(
        animation_owner,
        "apply_plan",
        record_snapshot_before_animation,
    )

    QTest.keyClick(box, Qt.Key.Key_Right)
    _process_events(app)

    assert _editor_reorder_preview_text(box) == "beta, alpha, gamma"
    assert observed_orders == [(1, 0, 2)]
    assert box.toPlainText() == "alpha, beta, gamma"

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)
