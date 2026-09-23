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

"""Verify reorder sweeps address overlapping targets without hiding misses."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, QRect, QRectF, QSizeF

from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementSnapshot,
    placement_for_drag_rect,
    reorder_placement_id_for_target,
)
from tools.prompt_editor_abuse.reorder_sweep_targeting import (
    pointer_for_reorder_sweep_placement,
)


def test_sweep_pointer_selects_blank_line_beside_overlapping_active_line() -> None:
    """A broad blank-line hit rect needs a point outside the active line lane."""

    line = _placement(
        PromptLineDropTarget(row_index=1, insertion_index=2),
        QRectF(116, 34, 627, 20),
        ordinal=5,
    )
    blank = _placement(
        PromptGapBlankLineDropTarget(gap_index=1, blank_line_index=1),
        QRectF(0, 36, 743, 16),
        ordinal=17,
    )
    snapshot = _snapshot(line, blank)
    assert (
        placement_for_drag_rect(
            snapshot,
            QRectF(346, 39, 50, 10),
            active_placement_id=line.placement_id,
        )
        == line
    )

    pointer = pointer_for_reorder_sweep_placement(
        snapshot,
        blank,
        drag_intent_size=QSizeF(50, 10),
        drag_grab_offset=QPointF(25, 5),
        pointer_bounds=QRect(0, 0, 743, 100),
        active_placement_id=line.placement_id,
    )

    assert blank.hit_rect.contains(QPointF(pointer))
    assert not line.hit_rect.contains(QPointF(pointer))
    assert (
        placement_for_drag_rect(
            snapshot,
            QRectF(pointer.x() - 25, pointer.y() - 5, 50, 10),
            active_placement_id=line.placement_id,
        )
        == blank
    )


def test_sweep_pointer_reports_a_genuinely_unreachable_target() -> None:
    """Do not silently skip a placement fully hidden by an active peer."""

    rect = QRectF(0, 36, 100, 16)
    line = _placement(
        PromptLineDropTarget(row_index=1, insertion_index=2), rect, ordinal=5
    )
    blank = _placement(
        PromptGapBlankLineDropTarget(gap_index=1, blank_line_index=1),
        rect,
        ordinal=17,
    )

    with pytest.raises(RuntimeError, match="no reachable pointer position"):
        pointer_for_reorder_sweep_placement(
            _snapshot(line, blank),
            blank,
            drag_intent_size=QSizeF(50, 10),
            drag_grab_offset=QPointF(25, 5),
            pointer_bounds=QRect(0, 0, 100, 100),
            active_placement_id=line.placement_id,
        )


def _placement(
    target: PromptReorderDropTarget,
    rect: QRectF,
    *,
    ordinal: int,
) -> PromptReorderPlacementGeometry:
    """Build one diagnostic placement with the target and hit area under test."""

    return PromptReorderPlacementGeometry(
        placement_id=reorder_placement_id_for_target(
            target, visual_line_index=2, ordinal=ordinal
        ),
        target=target,
        hit_rect=rect,
        insertion_anchor_rect=QRectF(rect.center().x(), rect.top(), 1, rect.height()),
        visual_line_rect=rect,
        expected_landing_rect=None,
        source_before=None,
        source_after=None,
    )


def _snapshot(
    line: PromptReorderPlacementGeometry,
    blank: PromptReorderPlacementGeometry,
) -> PromptReorderPlacementSnapshot:
    """Present both placements in the precedence order observed on Windows CI."""

    return PromptReorderPlacementSnapshot(
        placements=(line, blank),
        visual_line_count=3,
        layout_width=743,
        content_height=100,
    )
