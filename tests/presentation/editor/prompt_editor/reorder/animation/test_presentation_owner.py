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

"""Verify typed reorder animation presentation ownership."""

from __future__ import annotations

from typing import cast


from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderLayoutView,
    PromptReorderRowView,
)
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_displacement_intent import (
    ReorderDisplacementIntent,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometryId,
    PromptReorderChipGeometrySnapshot,
)


def _ensure_qapp() -> QApplication:
    """Return a running Qt application."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _visual(left: int) -> PromptChipVisual:
    """Return one deterministic prepared chip visual."""

    bubble = QRectF(float(left), 4.0, 30.0, 14.0)
    return PromptChipVisual(
        bubble_rects=(bubble,),
        fragment_union_rect=QRectF(bubble),
        hotspot_rect=QRect(left, 0, 40, 22),
        slot_before=QPointF(bubble.left(), bubble.center().y()),
        slot_after=QPointF(bubble.right(), bubble.center().y()),
        marker_height=bubble.height(),
    )


def _geometry(segment_index: int, left: int) -> PromptReorderChipGeometry:
    """Return minimal deterministic projection-owned chip geometry."""

    rect = QRect(left, 0, 40, 22)
    return PromptReorderChipGeometry(
        geometry_id=PromptReorderChipGeometryId(
            chip_index=segment_index,
            visual_revision=1,
        ),
        chip_index=segment_index,
        source_start=0,
        source_end=5,
        rendered_start=0,
        rendered_end=5,
        visual_lines=(),
        hotspot_rect=rect,
        chrome_path=QPainterPath(),
        outline_bounds=QRectF(rect),
        slot_before=QPointF(rect.left(), rect.center().y()),
        slot_after=QPointF(rect.right(), rect.center().y()),
        marker_height=float(rect.height()),
    )


def _geometry_snapshot() -> PromptReorderChipGeometrySnapshot:
    """Return settled geometry for two prepared chips."""

    return PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={
            0: _geometry(0, 60),
            1: _geometry(1, 100),
        },
        ordered_chip_indices=(0, 1),
        visual_line_count=1,
        layout_width=200.0,
        content_height=22.0,
        scroll_offset=0.0,
    )


def test_animation_presentation_owns_generation_and_visible_start_rects() -> None:
    """Target changes should publish generation truth and retained start geometry."""

    _ensure_qapp()
    parent = QWidget()
    try:
        owner = PromptReorderAnimationPresentationOwner(
            parent=parent,
            frame_callback=lambda: None,
        )
        target = PromptLineDropTarget(row_index=0, insertion_index=0)
        owner.record_target_change(
            ReorderDisplacementIntent(
                source="keyboard",
                held_segment_index=1,
                target=target,
                pointer_global_pos=None,
                reason="keyboard_target_changed",
            ),
            segment_indices=(0, 1),
            preview_active=True,
            live_visuals_by_index={0: _visual(0), 1: _visual(40)},
            preview_visuals_by_index={1: _visual(80)},
        )

        generation = owner.generation_state(
            geometry_generation_id=9,
            active_target=target,
        )
        assert generation.generation_id == 1
        assert generation.geometry_generation_id == 9
        assert generation.active_target == target
        assert owner.current_visible_chip_rects(
            segment_indices=(0, 1),
            preview_active=False,
            live_visuals_by_index={0: _visual(0), 1: _visual(40)},
            preview_visuals_by_index={},
        ) == {0: QRectF(0.0, 0.0, 40.0, 22.0)}
    finally:
        parent.deleteLater()


def test_animation_presentation_builds_and_counts_one_settled_plan() -> None:
    """Pending intent should become one plan through the sole planning owner."""

    _ensure_qapp()
    parent = QWidget()
    try:
        owner = PromptReorderAnimationPresentationOwner(
            parent=parent,
            frame_callback=lambda: None,
        )
        target = PromptLineDropTarget(row_index=0, insertion_index=0)
        owner.record_target_change(
            ReorderDisplacementIntent(
                source="pointer",
                held_segment_index=1,
                target=target,
                pointer_global_pos=None,
                reason="pointer_target_changed",
            ),
            segment_indices=(0, 1),
            preview_active=False,
            live_visuals_by_index={0: _visual(0), 1: _visual(40)},
            preview_visuals_by_index={},
        )

        plan = owner.build_plan_if_ready(
            current_visuals={0: QRectF(0.0, 0.0, 40.0, 22.0)},
            proposed_layout_view=PromptReorderLayoutView(
                rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1)),),
                gaps=(),
            ),
            preview_geometry=_geometry_snapshot(),
            ordered_segment_indices=(0, 1),
        )

        assert plan is not None
        assert plan.generation == 1
        assert plan.dragged_segment_index == 1
        assert tuple(target.segment_index for target in plan.changed_targets) == (0,)
        assert owner.counters()["animation_plan_build_count"] == 1
        assert (
            owner.build_plan_if_ready(
                current_visuals={},
                proposed_layout_view=None,
                preview_geometry=None,
                ordered_segment_indices=(0, 1),
            )
            is None
        )
        assert owner.counters()["animation_plan_build_count"] == 1
    finally:
        parent.deleteLater()
