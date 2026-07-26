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

"""Tests for authoritative prompt reorder drop-geometry construction."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.projection.reorder_drop_geometry_builder import (
    build_reorder_drop_geometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
    PromptReorderPlacementSnapshot,
)


def test_drop_geometry_keeps_targets_across_regional_partitions() -> None:
    """Every structural destination should remain available during a regional drag."""

    snapshot = PromptReorderPlacementSnapshot(
        placements=(_placement(0), _placement(1)),
        visual_line_count=2,
        layout_width=320.0,
        content_height=80.0,
    )

    geometry = build_reorder_drop_geometry(snapshot)

    expected_targets = (
        PromptLineDropTarget(row_index=0, insertion_index=0),
        PromptLineDropTarget(row_index=1, insertion_index=0),
    )
    assert (
        tuple(placement.target for placement in geometry.placement_snapshot.placements)
        == expected_targets
    )
    assert (
        tuple(visual.target for visual in geometry.target_visuals) == expected_targets
    )
    assert (
        tuple(
            visual.target
            for lane in geometry.lanes
            for visual in getattr(lane, "slot_visuals", ())
        )
        == expected_targets
    )


def _placement(row_index: int) -> PromptReorderPlacementGeometry:
    """Return one deterministic line placement for a source row."""

    target = PromptLineDropTarget(row_index=row_index, insertion_index=0)
    rect = QRectF(0.0, float(row_index * 20), 100.0, 20.0)
    return PromptReorderPlacementGeometry(
        placement_id=PromptReorderPlacementId(
            target_kind="line",
            row_index=row_index,
            insertion_index=0,
            gap_index=None,
            blank_line_index=None,
            visual_line_index=row_index,
            ordinal=row_index,
        ),
        target=target,
        hit_rect=rect,
        insertion_anchor_rect=rect,
        visual_line_rect=rect,
        expected_landing_rect=None,
        source_before=None,
        source_after=None,
    )
