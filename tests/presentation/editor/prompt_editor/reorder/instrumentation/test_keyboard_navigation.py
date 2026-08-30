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

"""Verify prompt reorder keyboard navigation instrumentation contracts."""

from __future__ import annotations

from typing import Any, cast

import pytest


from PySide6.QtCore import QRectF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
)
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


def test_reorder_keyboard_preview_does_not_mutate_source_until_alt_release(
    widgets: list[QWidget],
) -> None:
    """Keyboard reorder preview should stay display-only before Alt release."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8)
    box.setTextCursor(cursor)
    can_undo_before = box.canUndo()

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)

    assert _editor_reorder_preview_text(box) == "beta, alpha, gamma"
    assert box.toPlainText() == "alpha, beta, gamma"
    assert box.canUndo() is can_undo_before

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)

    assert box.toPlainText() == "beta, alpha, gamma"


def test_reorder_keyboard_end_of_line_separator_uses_preceding_chip(
    widgets: list[QWidget],
) -> None:
    """Alt+Arrow at a trailing comma/newline should move the preceding chip."""

    app = _ensure_qapp()
    text = (
        "1girl, (mature female:1.10), floating, black bident, parted lips, "
        "holding double helix spear, see-through silhouette, contrapposto, \n"
    )
    box = _create_prompt_editor(widgets, text=text, width=760, height=260)
    cursor = box.textCursor()
    cursor.setPosition(len(text))
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))

    assert overlay.active_segment_index() == 7
    before = _performance_counters(overlay)

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)
    after = _performance_counters(overlay)

    assert overlay.ordered_chip_indices() == [0, 1, 2, 3, 4, 5, 7, 6]
    assert _counter_delta(before, after, "animation_plan_build_count") == 1
    assert _counter_delta(before, after, "animation_plan_applied_count") == 1
    assert _editor_reorder_preview_text(box) == (
        "1girl, (mature female:1.10), floating, black bident, parted lips, "
        "holding double helix spear, contrapposto, see-through silhouette, "
    )
    assert box.toPlainText() == text

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


@pytest.mark.parametrize(
    "movement_key",
    [Qt.Key.Key_Down, Qt.Key.Key_Right],
)
def test_reorder_keyboard_targets_blank_line_before_next_populated_row(
    widgets: list[QWidget],
    movement_key: Qt.Key,
) -> None:
    """Alt+Arrow should target a prepared blank-line lane before the next chip row."""

    app = _ensure_qapp()
    text = (
        "empty eyes, sharp teeth, halo behind head, too many rabbits,\n\nbacklighting,"
    )
    box = _create_prompt_editor(widgets, text=text, width=520, height=260)
    cursor = box.textCursor()
    cursor.setPosition(text.index("too many rabbits") + 2)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    before = _performance_counters(overlay)

    QTest.keyClick(box, movement_key)
    _process_events(app)
    after = _performance_counters(overlay)

    assert (
        overlay.preview_build_facts.snapshot().drop_target
        == PromptGapBlankLineDropTarget(
            gap_index=0,
            blank_line_index=0,
        )
    )
    expected_reordered_text = (
        "empty eyes, sharp teeth, halo behind head, \ntoo many rabbits,\nbacklighting,"
    )
    assert _editor_reorder_preview_text(box) == expected_reordered_text
    assert box.toPlainText() == text
    assert _counter_delta(before, after, "animation_plan_build_count") == 1
    assert _counter_delta(before, after, "animation_plan_applied_count") == 1

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)
    assert box.toPlainText() == expected_reordered_text


def test_reorder_vertical_keyboard_move_animates_to_lane_geometry(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alt+Up should animate visible chips to projection-owned target lane rects."""

    app = _ensure_qapp()
    box = _create_prompt_editor(
        widgets,
        width=380,
        height=240,
        text="alpha,\n\n\ngamma, beta",
    )
    cursor = box.textCursor()
    cursor.setPosition(len("alpha,\n\n\ngamma, beta"))
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    animation_owner = cast(Any, overlay)._animation_presentation
    original_apply_plan = animation_owner.apply_plan
    recorded_plans: list[Any] = []

    def record_apply_plan(plan: Any, **context: Any) -> None:
        """Record vertical keyboard plans while preserving presenter behavior."""

        recorded_plans.append(plan)
        original_apply_plan(plan, **context)

    monkeypatch.setattr(animation_owner, "apply_plan", record_apply_plan)
    before = _performance_counters(overlay)

    QTest.keyClick(box, Qt.Key.Key_Up)
    _process_events(app)
    after = _performance_counters(overlay)

    assert _editor_reorder_preview_text(box) == "alpha,\n\nbeta,\ngamma"
    assert recorded_plans
    assert recorded_plans[-1].dragged_segment_index == 2
    assert recorded_plans[-1].changed_targets == ()
    assert _counter_delta(before, after, "held_animation_started_count") == 1
    held_overrides = cast(
        Any, overlay
    )._animation_presentation.publication.held_rects_by_index
    assert set(held_overrides) == {2}
    target_rect = overlay.preview_rect_for_segment(2)
    assert target_rect is not None
    assert held_overrides[2] != QRectF(target_rect)
    for target in recorded_plans[-1].changed_targets:
        preview_rect_value = overlay.preview_rect_for_segment(target.segment_index)
        assert preview_rect_value is not None
        preview_rect = QRectF(preview_rect_value)
        assert target.target_rect.left() == preview_rect.left()
        assert target.target_rect.top() == preview_rect.top()
        assert target.target_rect.width() == preview_rect.width()
        assert target.target_rect.height() == preview_rect.height()

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_keyboard_boundary_noop_builds_no_animation_plan(
    widgets: list[QWidget],
) -> None:
    """Boundary Alt+Arrow no-ops should not advance animation planning."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(2)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)
    overlay = cast(SegmentReorderOverlay, getattr(box, "_segment_overlay"))
    before = _performance_counters(overlay)

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)
    after = _performance_counters(overlay)

    assert _editor_reorder_preview_text(box) == "alpha, beta, gamma"
    assert overlay.ordered_chip_indices() == [0, 1, 2]
    assert _counter_delta(before, after, "animation_plan_build_count") == 0
    assert _counter_delta(before, after, "animation_plan_applied_count") == 0

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)
