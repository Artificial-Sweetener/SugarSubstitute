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

"""Verify prompt reorder keyboard animation transitions instrumentation contracts."""

from __future__ import annotations

from typing import Any, cast

import pytest


from PySide6.QtCore import Qt
from PySide6.QtGui import QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    SegmentReorderOverlay,
)

from tests.support.prompt_editor.projection_engine_support import surface_for

from .support import (
    _counter_delta,
    _create_prompt_editor,
    _ensure_qapp,
    _performance_counters,
    _process_events,
)


def test_reorder_keyboard_suppression_clips_settled_projection(
    widgets: list[QWidget],
) -> None:
    """Alt+Arrow overlay ownership should hide settled projection chip paint."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8)
    box.setTextCursor(cursor)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    _process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Left)
    _process_events(app)

    surface = surface_for(box)
    visible_region = cast(Any, surface)._preview_visible_region()

    assert set(
        cast(
            Any,
            surface,
        )._reorder_surface_visual_state.state.suppression_snapshots_by_index
    ) == {0, 1}
    assert visible_region is not None
    hidden_region = QRegion(surface.viewport().rect()).subtracted(visible_region)
    assert not hidden_region.isEmpty()

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_keyboard_blank_line_animation_survives_overlay_resize(
    widgets: list[QWidget],
) -> None:
    """Preview-owned overlay resizes should not settle blank-line animations."""

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
    animation_owner = cast(Any, overlay)._animation_presentation
    animation_owner.set_duration_ms(1000)

    QTest.keyClick(box, Qt.Key.Key_Down)
    _process_events(app)

    assert (
        overlay.preview_build_facts.snapshot().drop_target
        == PromptGapBlankLineDropTarget(
            gap_index=0,
            blank_line_index=0,
        )
    )
    assert animation_owner.publication.paint_rects_by_index
    before = _performance_counters(overlay)

    overlay.resize(overlay.width() + 1, overlay.height() + 1)
    _process_events(app)
    after = _performance_counters(overlay)

    assert _counter_delta(before, after, "animation_settled_count") == 0
    assert _counter_delta(before, after, "held_animation_settled_count") == 0
    assert animation_owner.publication.paint_rects_by_index

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)


def test_reorder_keyboard_return_from_blank_line_still_animates(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returning to original order should still animate the active preview target."""

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
    animation_owner = cast(Any, overlay)._animation_presentation
    animation_owner.set_duration_ms(1000)

    QTest.keyClick(box, Qt.Key.Key_Down)
    _process_events(app)

    assert overlay.has_reordered() is True
    assert (
        overlay.preview_build_facts.snapshot().drop_target
        == PromptGapBlankLineDropTarget(
            gap_index=0,
            blank_line_index=0,
        )
    )
    monkeypatch.setattr(overlay, "has_reordered", lambda: False)
    before_return = _performance_counters(overlay)

    QTest.keyClick(box, Qt.Key.Key_Up)
    _process_events(app)
    after_return = _performance_counters(overlay)

    assert overlay.has_reordered() is False
    assert (
        _counter_delta(before_return, after_return, "animation_plan_build_count") == 1
    )
    assert (
        _counter_delta(before_return, after_return, "animation_plan_applied_count") == 1
    )
    assert animation_owner.publication.paint_rects_by_index

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    _process_events(app)
