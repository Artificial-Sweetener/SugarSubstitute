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

"""Cover authoritative reorder preview paint-snapshot publication."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QPointF, QRect, QRectF

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderPreviewSnapshot,
)
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_paint_snapshot_owner import (
    PromptReorderPreviewPaintSnapshotOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometrySnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
)


class _Geometry:
    """Publish replaceable immutable preview geometry state."""

    def __init__(self) -> None:
        """Initialize one complete preview publication."""

        self.state = PromptReorderInteractionGeometryState(
            preview_chip_geometry_snapshot=PromptReorderChipGeometrySnapshot(
                geometries_by_chip_index={},
                ordered_chip_indices=(0,),
                visual_line_count=1,
                layout_width=200.0,
                content_height=24.0,
                scroll_offset=0.0,
            ),
            preview_snapshot=PromptReorderPreviewSnapshot(
                text="alpha",
                chip_ranges_by_index={0: (0, 5)},
                chip_rendered_ranges_by_index={0: (0, 5)},
                chip_owned_ranges_by_index={0: ((0, 5),)},
                gap_ranges_by_index={},
            ),
        )


class _Visuals:
    """Expose deterministic prepared preview visuals."""

    def __init__(self, visuals: Mapping[int, PromptChipVisual]) -> None:
        """Store supplied visual facts."""

        self.visuals_by_index = visuals


class _Editor:
    """Record projection snapshot requests and return deterministic snapshots."""

    def __init__(self) -> None:
        """Initialize no requests."""

        self.requests: list[frozenset[int] | None] = []

    def reorder_preview_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        chip_indices: frozenset[int] | None = None,
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return snapshots for requested known and unknown indices."""

        assert chip_geometry_snapshot.ordered_chip_indices == (0,)
        assert chip_owned_ranges_by_index == {0: ((0, 5),)}
        self.requests.append(chip_indices)
        return {index: _projection_snapshot(index) for index in (chip_indices or ())}


def test_preview_paint_snapshot_owner_binds_only_complete_visuals() -> None:
    """Projection snapshots without matching prepared visuals must be omitted."""

    editor = _Editor()
    owner = PromptReorderPreviewPaintSnapshotOwner(
        build_projection_snapshots=(
            editor.reorder_preview_chip_projection_paint_snapshots
        ),
        geometry_state=lambda: _Geometry().state,
        preview_visuals=lambda: _Visuals({0: _visual()}).visuals_by_index,
    )

    owner.prepare(frozenset({0, 1}))

    assert editor.requests == [frozenset({0, 1})]
    assert tuple(owner.snapshots_by_index) == (0,)
    assert owner.snapshots_by_index[0].projection_snapshot.key.segment_index == 0


def test_preview_paint_snapshot_owner_clears_without_projection_work() -> None:
    """An empty request should discard stale snapshots without querying paint."""

    editor = _Editor()
    owner = PromptReorderPreviewPaintSnapshotOwner(
        build_projection_snapshots=(
            editor.reorder_preview_chip_projection_paint_snapshots
        ),
        geometry_state=lambda: _Geometry().state,
        preview_visuals=lambda: _Visuals({0: _visual()}).visuals_by_index,
    )
    owner.prepare(frozenset({0}))

    owner.prepare(frozenset())

    assert owner.snapshots_by_index == {}
    assert editor.requests == [frozenset({0})]


def _visual() -> PromptChipVisual:
    """Return one deterministic preview visual."""

    bubble = QRectF(8.0, 6.0, 48.0, 20.0)
    return PromptChipVisual(
        bubble_rects=(bubble,),
        fragment_union_rect=QRectF(bubble),
        hotspot_rect=QRect(4, 4, 56, 24),
        slot_before=QPointF(8.0, 16.0),
        slot_after=QPointF(56.0, 16.0),
        marker_height=20.0,
    )


def _projection_snapshot(segment_index: int) -> PromptReorderProjectionPaintSnapshot:
    """Return one empty immutable projection paint snapshot."""

    return PromptReorderProjectionPaintSnapshot(
        key=PromptReorderProjectionSnapshotKey(
            source_revision=1,
            viewport_rect=QRect(0, 0, 320, 180),
            scroll_offset=0,
            font_key="test",
            palette_key=1,
            preview_generation=1,
            geometry_generation=1,
            segment_index=segment_index,
            mode="preview",
        ),
        fragments=(),
        source_ranges=((0, 5),),
        content_key=("preview", segment_index),
    )
