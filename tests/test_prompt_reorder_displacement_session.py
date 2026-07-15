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

"""Cover shared pointer/keyboard reorder displacement session ownership."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF

from substitute.application.prompt_editor import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.overlays.reorder_displacement_intent import (
    ReorderDisplacementIntent,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_displacement_session import (
    ReorderDisplacementSession,
)


def test_displacement_session_records_held_segment_and_start_rects() -> None:
    """A target change should preserve held identity and pre-layout rects."""

    session = ReorderDisplacementSession()
    target = PromptLineDropTarget(row_index=0, insertion_index=1)

    pending = session.record_target_change(
        ReorderDisplacementIntent(
            source="keyboard",
            held_segment_index=2,
            target=target,
            pointer_global_pos=None,
            reason="keyboard_target_changed",
        ),
        generation=4,
        previous_visible_rects={
            1: QRectF(0.0, 0.0, 20.0, 10.0),
            2: QRectF(24.0, 0.0, 20.0, 10.0),
        },
    )

    assert pending is not None
    assert pending.held_segment_index == 2
    assert pending.source == "keyboard"
    assert session.state.active is True
    assert session.state.held_segment_index == 2
    assert session.state.previous_visible_rects[2] == QRectF(24.0, 0.0, 20.0, 10.0)


def test_displacement_session_consumes_only_matching_target() -> None:
    """Stale target changes should not build an animation plan."""

    session = ReorderDisplacementSession()
    pending_target = PromptLineDropTarget(row_index=0, insertion_index=1)
    active_target = PromptLineDropTarget(row_index=0, insertion_index=2)
    session.record_target_change(
        ReorderDisplacementIntent(
            source="pointer",
            held_segment_index=1,
            target=pending_target,
            pointer_global_pos=QPoint(10, 10),
            reason="pointer_target_changed",
        ),
        generation=3,
        previous_visible_rects={},
    )

    assert session.consume_pending_target(active_target=active_target) is None
    assert session.consume_pending_target(active_target=pending_target) is None


def test_displacement_session_clear_preserves_generation_watermarks() -> None:
    """Clearing displacement should not rewind generation counters."""

    session = ReorderDisplacementSession()
    session.clear(preview_generation=7, animation_generation=9, raster_generation=11)

    assert session.state.active is False
    assert session.state.preview_generation == 7
    assert session.state.animation_generation == 9
    assert session.state.raster_generation == 11
    assert session.bump_raster_generation() == 12
