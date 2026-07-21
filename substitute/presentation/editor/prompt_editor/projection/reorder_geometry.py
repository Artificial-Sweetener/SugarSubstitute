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

"""Own projection-derived reorder chip, row, and placement geometry."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QRectF, QSizeF

from substitute.application.prompt_editor import (
    PromptGapBlankLineDropTarget,
    PromptReorderGapView,
    PromptReorderLayoutView,
    blank_line_drop_offsets,
)

from .model import PromptProjectionDocument, PromptProjectionSelection
from .observability import log_reorder_drag_event
from .reorder_chip_geometry import (
    PromptReorderChipFragment,
    PromptReorderChipGeometry,
    PromptReorderChipGeometrySnapshot,
    PromptReorderChipLineGeometry,
    chip_geometry_context,
)
from .reorder_chip_geometry_builder import build_reorder_chip_geometry
from .reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementSnapshot,
    reorder_placement_id_for_target,
)
from .reorder_placement_geometry_builder import build_row_reorder_placements
from .snapshot import PromptProjectionLayoutSnapshot, PromptProjectionLineSnapshot
from .visible_line_range import (
    PromptProjectionSourceLineIndex,
    source_range_intersects_visual_line,
    visible_projection_lines,
)


class PromptProjectionSourceRangeFragmentProvider(Protocol):
    """Provide generic source-range fragments from prepared projection lines."""

    def source_range_fragments_for_line(
        self,
        line: PromptProjectionLineSnapshot,
        *,
        selection: PromptProjectionSelection,
        range_start: int,
        range_end: int,
    ) -> tuple[QRectF, ...]:
        """Return merged document-space fragments from one visual line."""


@dataclass(frozen=True, slots=True)
class PromptProjectionReorderGeometryState:
    """Supply immutable prepared layout state needed by reorder geometry."""

    projection_document: PromptProjectionDocument
    layout_snapshot: PromptProjectionLayoutSnapshot
    content_size: QSizeF
    fallback_caret_rect: QRectF
    source_fragments: PromptProjectionSourceRangeFragmentProvider


@dataclass(frozen=True, slots=True)
class PromptProjectionReorderGeometry:
    """Derive all reorder geometry without retaining the mutable layout engine."""

    def reorder_chip_geometry_snapshot(
        self,
        *,
        state: PromptProjectionReorderGeometryState,
        layout_view: PromptReorderLayoutView,
        chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        viewport_rect: QRectF,
        scroll_offset: float,
        included_chip_indices: frozenset[int] | None = None,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return one projection-owned geometry object per semantic reorder chip."""

        _ = chip_owned_ranges_by_index
        snapshot = state.layout_snapshot
        line_rects = _viewport_line_rects(
            snapshot.lines,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        visible_lines = visible_projection_lines(
            snapshot.lines,
            document_top=viewport_rect.top() + scroll_offset,
            document_bottom=viewport_rect.bottom() + scroll_offset,
        )
        visible_source_lines = PromptProjectionSourceLineIndex(visible_lines)
        visible_source_bounds = (
            None
            if not visible_lines
            else (
                min(line.source_start for line in visible_lines),
                max(line.source_end for line in visible_lines),
            )
        )
        visible_line_identities = {id(line) for line in visible_lines}
        visual_line_indices_by_identity = {
            id(line): line_index
            for line_index, line in enumerate(snapshot.lines)
            if id(line) in visible_line_identities
        }
        ordered_chip_indices = tuple(
            chip_index for row in layout_view.rows for chip_index in row.chip_indices
        )
        geometries: dict[int, PromptReorderChipGeometry] = {}
        for visual_revision, chip_index in enumerate(ordered_chip_indices):
            if (
                included_chip_indices is not None
                and chip_index not in included_chip_indices
            ):
                continue
            rendered_range = chip_rendered_ranges_by_index.get(chip_index)
            if rendered_range is None:
                log_reorder_drag_event(
                    "anomaly.chip_geometry_missing_range",
                    chip_index=chip_index,
                )
                continue
            range_start, range_end = rendered_range
            if visible_source_bounds is None:
                continue
            visible_source_start, visible_source_end = visible_source_bounds
            if range_end < visible_source_start or range_start > visible_source_end:
                continue
            fragments = self._visible_reorder_fragments(
                state,
                range_start,
                range_end,
                visible_lines=visible_source_lines.lines_intersecting(
                    range_start,
                    range_end,
                ),
                visual_line_indices_by_identity=visual_line_indices_by_identity,
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
            )
            log_reorder_drag_event(
                "chip_geometry.fragment_inputs",
                chip_index=chip_index,
                rendered_start=range_start,
                rendered_end=range_end,
                fragment_count=len(fragments),
            )
            if not fragments:
                log_reorder_drag_event(
                    "anomaly.chip_geometry_missing",
                    chip_index=chip_index,
                    rendered_start=range_start,
                    rendered_end=range_end,
                )
                continue
            geometry = build_reorder_chip_geometry(
                chip_index=chip_index,
                visual_revision=visual_revision,
                rendered_start=range_start,
                rendered_end=range_end,
                fragments=fragments,
                viewport_rect=viewport_rect,
                line_rects=line_rects,
            )
            if geometry.chrome_path.isEmpty():
                log_reorder_drag_event(
                    "anomaly.chip_geometry_empty_path",
                    chip_index=chip_index,
                    rendered_start=range_start,
                    rendered_end=range_end,
                )
            geometries[chip_index] = geometry
            log_reorder_drag_event(
                "chip_geometry.chip",
                **chip_geometry_context(geometry),
            )

        duplicate_chip_count = len(ordered_chip_indices) - len(
            set(ordered_chip_indices)
        )
        if duplicate_chip_count:
            log_reorder_drag_event(
                "anomaly.chip_geometry_duplicate",
                geometry_count=len(geometries),
                duplicate_chip_count=duplicate_chip_count,
            )
        log_reorder_drag_event(
            "chip_geometry.snapshot",
            geometry_count=len(geometries),
            ordered_count=len(ordered_chip_indices),
            visual_line_count=len(snapshot.lines),
            layout_width=f"{viewport_rect.width():.2f}",
            content_height=f"{state.content_size.height():.2f}",
            scroll_offset=f"{scroll_offset:.2f}",
        )
        return PromptReorderChipGeometrySnapshot(
            geometries_by_chip_index=geometries,
            ordered_chip_indices=ordered_chip_indices,
            visual_line_count=len(snapshot.lines),
            layout_width=float(viewport_rect.width()),
            content_height=float(state.content_size.height()),
            scroll_offset=float(scroll_offset),
        )

    def reorder_placement_snapshot(
        self,
        *,
        state: PromptProjectionReorderGeometryState,
        layout_view: PromptReorderLayoutView,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptReorderPlacementSnapshot:
        """Return placement geometry derived from projection-owned chip geometry."""

        snapshot = state.layout_snapshot
        placements: list[PromptReorderPlacementGeometry] = []
        ordinal = 0
        line_rects = _viewport_line_rects(
            snapshot.lines,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        log_reorder_drag_event(
            "placement_geometry.uses_chip_geometry_snapshot",
            chip_geometry_count=len(chip_geometry_snapshot.geometries_by_chip_index),
            ordered_chip_count=len(chip_geometry_snapshot.ordered_chip_indices),
            row_count=len(layout_view.rows),
            gap_count=len(layout_view.gaps),
        )

        for row in layout_view.rows:
            row_line_items: dict[
                int,
                list[
                    tuple[
                        int,
                        PromptReorderChipGeometry,
                        PromptReorderChipLineGeometry,
                    ]
                ],
            ] = {}
            for segment_index in row.chip_indices:
                geometry = chip_geometry_snapshot.geometries_by_chip_index.get(
                    segment_index
                )
                if geometry is None:
                    log_reorder_drag_event(
                        "anomaly.placement_missing_chip_geometry",
                        row_index=row.row_index,
                        chip_index=segment_index,
                        chip_geometry_count=len(
                            chip_geometry_snapshot.geometries_by_chip_index
                        ),
                    )
                    continue
                for line_geometry in geometry.visual_lines:
                    row_line_items.setdefault(
                        line_geometry.visual_line_index,
                        [],
                    ).append((segment_index, geometry, line_geometry))

            for visual_line_index, line_items in sorted(row_line_items.items()):
                line_rect = line_rects.get(visual_line_index)
                if line_rect is None or line_rect.isEmpty():
                    continue
                line_items.sort(key=lambda item: item[2].content_rect.center().x())
                placement_items = build_row_reorder_placements(
                    row_indices=row.chip_indices,
                    line_items=line_items,
                    row_index=row.row_index,
                    visual_line_index=visual_line_index,
                    visual_line_rect=line_rect,
                    viewport_rect=viewport_rect,
                    ordinal_start=ordinal,
                )
                placements.extend(placement_items)
                ordinal += len(placement_items)

        for gap in layout_view.gaps:
            gap_range = gap_ranges_by_index.get(gap.gap_index)
            if gap_range is None:
                continue
            gap_start, _gap_end = gap_range
            for blank_line_index in range(gap.blank_line_count):
                source_position = gap_start + _gap_blank_line_offset(
                    gap,
                    blank_line_index,
                )
                caret_rect = _cursor_rect_for_source_position(
                    state,
                    source_position,
                    scroll_offset=scroll_offset,
                )
                if caret_rect.isEmpty():
                    continue
                visual_line_index_or_none = _visual_line_index_for_viewport_y(
                    snapshot.lines,
                    caret_rect.center().y(),
                    scroll_offset=scroll_offset,
                )
                if visual_line_index_or_none is None:
                    visual_line_index = max(0, len(snapshot.lines) - 1)
                else:
                    visual_line_index = visual_line_index_or_none
                visual_line_rect = line_rects.get(
                    visual_line_index,
                    QRectF(
                        viewport_rect.left(),
                        caret_rect.top(),
                        viewport_rect.width(),
                        max(1.0, caret_rect.height()),
                    ),
                )
                hit_rect = QRectF(
                    viewport_rect.left(),
                    caret_rect.top(),
                    viewport_rect.width(),
                    max(1.0, caret_rect.height()),
                ).intersected(viewport_rect)
                if hit_rect.isEmpty():
                    continue
                target = PromptGapBlankLineDropTarget(
                    gap_index=gap.gap_index,
                    blank_line_index=blank_line_index,
                )
                placements.append(
                    PromptReorderPlacementGeometry(
                        placement_id=reorder_placement_id_for_target(
                            target,
                            visual_line_index=visual_line_index,
                            ordinal=ordinal,
                        ),
                        target=target,
                        hit_rect=hit_rect,
                        insertion_anchor_rect=caret_rect,
                        visual_line_rect=visual_line_rect,
                        expected_landing_rect=None,
                        source_before=gap_start,
                        source_after=gap_start,
                    )
                )
                ordinal += 1

        return PromptReorderPlacementSnapshot(
            placements=tuple(placements),
            visual_line_count=len(snapshot.lines),
            layout_width=float(viewport_rect.width()),
            content_height=float(state.content_size.height()),
        )

    def source_range_row_rects(
        self,
        state: PromptProjectionReorderGeometryState,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return full-width visible row rects intersecting one source range."""

        range_start = max(0, min(start, end))
        range_end = max(0, max(start, end))
        row_rects: list[QRectF] = []
        for line in state.layout_snapshot.lines:
            if not source_range_intersects_visual_line(
                source_start=range_start,
                source_end=range_end,
                visual_start=line.source_start,
                visual_end=line.source_end,
            ):
                continue
            viewport_line_rect = QRectF(
                viewport_rect.left(),
                line.top - scroll_offset,
                viewport_rect.width(),
                line.height,
            )
            clipped_rect = viewport_line_rect.intersected(viewport_rect)
            if clipped_rect.isValid() and not clipped_rect.isEmpty():
                row_rects.append(viewport_line_rect)
        return tuple(row_rects)

    @staticmethod
    def _visible_reorder_fragments(
        state: PromptProjectionReorderGeometryState,
        start: int,
        end: int,
        *,
        visible_lines: tuple[PromptProjectionLineSnapshot, ...],
        visual_line_indices_by_identity: dict[int, int],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[PromptReorderChipFragment, ...]:
        """Return viewport fragments while retaining their visual-line identity."""

        range_start = max(0, start)
        range_end = max(0, end)
        if range_end <= range_start:
            return ()
        selection = PromptProjectionSelection(range_start, range_end)
        visible_fragments: list[PromptReorderChipFragment] = []
        for line in visible_lines:
            visual_line_index = visual_line_indices_by_identity[id(line)]
            for rect in state.source_fragments.source_range_fragments_for_line(
                line,
                selection=selection,
                range_start=range_start,
                range_end=range_end,
            ):
                clipped_rect = rect.translated(0.0, -scroll_offset).intersected(
                    viewport_rect
                )
                if clipped_rect.isValid() and not clipped_rect.isEmpty():
                    visible_fragments.append(
                        PromptReorderChipFragment(
                            visual_line_index=visual_line_index,
                            rect=clipped_rect,
                        )
                    )
        return tuple(visible_fragments)


def _viewport_line_rects(
    lines: Sequence[PromptProjectionLineSnapshot],
    *,
    viewport_rect: QRectF,
    scroll_offset: float,
) -> dict[int, QRectF]:
    """Return viewport-local full-width rects for visible projection lines."""

    line_rects: dict[int, QRectF] = {}
    for line_index, line in enumerate(lines):
        line_rect = QRectF(
            viewport_rect.left(),
            line.top - scroll_offset,
            viewport_rect.width(),
            line.height,
        ).intersected(viewport_rect)
        if line_rect.isValid() and not line_rect.isEmpty():
            line_rects[line_index] = line_rect
    return line_rects


def _cursor_rect_for_source_position(
    state: PromptProjectionReorderGeometryState,
    source_position: int,
    *,
    scroll_offset: float,
) -> QRectF:
    """Return the viewport caret rect for one source position."""

    caret_map = state.projection_document.caret_map
    caret_state = caret_map.resolve_state(
        caret_map.state_for_source_position(source_position)
    )
    projection_position = caret_map.projection_position_for_state(caret_state)
    rect = state.layout_snapshot.caret_rects_by_projection_position.get(
        projection_position
    )
    if rect is None:
        nearest_stop = _nearest_caret_stop(
            state.layout_snapshot.lines,
            projection_position,
        )
        rect = state.fallback_caret_rect if nearest_stop is None else nearest_stop
    return QRectF(rect).translated(0.0, -scroll_offset)


def _nearest_caret_stop(
    lines: Sequence[PromptProjectionLineSnapshot],
    projection_position: int,
) -> QRectF | None:
    """Return the nearest prepared caret rect by projection distance."""

    nearest_rect: QRectF | None = None
    nearest_distance: int | None = None
    for line in lines:
        for caret_stop in line.caret_stops:
            distance = abs(caret_stop.projection_position - projection_position)
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest_rect = caret_stop.rect
    return nearest_rect


def _visual_line_index_for_viewport_y(
    lines: Sequence[PromptProjectionLineSnapshot],
    y_position: float,
    *,
    scroll_offset: float,
) -> int | None:
    """Return the visual line nearest one viewport-local Y value."""

    document_y = y_position + scroll_offset
    containing_indices = [
        line_index
        for line_index, line in enumerate(lines)
        if (line.top - 1.0) <= document_y <= ((line.top + line.height) + 1.0)
    ]
    if containing_indices:
        return containing_indices[0]
    best_line_index: int | None = None
    best_distance: float | None = None
    for line_index, line in enumerate(lines):
        distance = _axis_distance(
            axis_value=document_y,
            start=line.top,
            end=line.top + line.height,
        )
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_line_index = line_index
    return best_line_index


def _axis_distance(*, axis_value: float, start: float, end: float) -> float:
    """Return the distance from one coordinate to one closed interval."""

    if axis_value < start:
        return start - axis_value
    if axis_value > end:
        return axis_value - end
    return 0.0


def _gap_blank_line_offset(gap: PromptReorderGapView, blank_line_index: int) -> int:
    """Return the source offset for one blank-line target inside a gap."""

    offsets = blank_line_drop_offsets(gap.separator_text)
    if not 0 <= blank_line_index < len(offsets):
        return 0
    return offsets[blank_line_index]


__all__ = [
    "PromptProjectionReorderGeometry",
    "PromptProjectionReorderGeometryState",
    "PromptProjectionSourceRangeFragmentProvider",
]
