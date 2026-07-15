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

"""Describe projection-owned geometry for prompt segment reorder placement."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import QPointF, QRectF, QSizeF

from substitute.application.prompt_editor import (
    PromptLineDropTarget,
    PromptReorderDropTarget,
)

from .observability import (
    log_reorder_drag_timing,
    reorder_drag_point_context,
    reorder_drag_rect_context,
    reorder_drag_started_at,
    reorder_drag_target_kind,
)


@dataclass(frozen=True, slots=True)
class PromptReorderPlacementId:
    """Identify one visible reorder placement in diagnostic-safe form."""

    target_kind: str
    row_index: int | None
    insertion_index: int | None
    gap_index: int | None
    blank_line_index: int | None
    visual_line_index: int
    ordinal: int


@dataclass(frozen=True, slots=True)
class PromptReorderPlacementGeometry:
    """Describe one reorder target and its projection-owned geometry."""

    placement_id: PromptReorderPlacementId
    target: PromptReorderDropTarget
    hit_rect: QRectF
    insertion_anchor_rect: QRectF
    visual_line_rect: QRectF
    expected_landing_rect: QRectF | None
    source_before: int | None
    source_after: int | None
    adjacent_chip_indices: tuple[int, ...] = ()
    expected_landing_chip_index: int | None = None
    expected_landing_bounds: QRectF | None = None

    def with_expected_landing_rect(
        self,
        expected_landing_rect: QRectF | None,
    ) -> "PromptReorderPlacementGeometry":
        """Return this placement with preview-derived landing geometry attached."""

        return replace(
            self,
            expected_landing_rect=expected_landing_rect,
            expected_landing_bounds=expected_landing_rect,
        )

    def with_expected_landing_geometry(
        self,
        *,
        chip_index: int,
        expected_landing_bounds: QRectF,
    ) -> "PromptReorderPlacementGeometry":
        """Return this placement with semantic chip landing geometry attached."""

        return replace(
            self,
            expected_landing_rect=expected_landing_bounds,
            expected_landing_chip_index=chip_index,
            expected_landing_bounds=expected_landing_bounds,
        )


@dataclass(frozen=True, slots=True)
class PromptReorderPlacementSnapshot:
    """Describe all visible reorder placements for one projection layout state."""

    placements: tuple[PromptReorderPlacementGeometry, ...]
    visual_line_count: int
    layout_width: float
    content_height: float

    def placement_for_target(
        self,
        target: PromptReorderDropTarget | None,
    ) -> PromptReorderPlacementGeometry | None:
        """Return the first placement matching the supplied target."""

        if target is None:
            return None
        for placement in self.placements:
            if placement.target == target:
                return placement
        return None

    def placement_for_id(
        self,
        placement_id: PromptReorderPlacementId | None,
    ) -> PromptReorderPlacementGeometry | None:
        """Return the placement with the supplied stable identity."""

        if placement_id is None:
            return None
        for placement in self.placements:
            if placement.placement_id == placement_id:
                return placement
        return None


def duplicate_reorder_placement_targets(
    snapshot: PromptReorderPlacementSnapshot,
) -> tuple[str, ...]:
    """Return duplicate reorder target identities in one placement snapshot."""

    seen_targets: set[str] = set()
    duplicate_targets: list[str] = []
    for placement in snapshot.placements:
        target = reorder_drag_target_kind(placement.target)
        target_key = (
            f"{target}:"
            f"{placement.source_before}:"
            f"{placement.source_after}:"
            f"{placement.placement_id.visual_line_index}:"
            f"{placement.placement_id.ordinal}"
        )
        if target_key in seen_targets:
            duplicate_targets.append(target)
            continue
        seen_targets.add(target_key)
    return tuple(duplicate_targets)


def reorder_placement_id_for_target(
    target: PromptReorderDropTarget,
    *,
    visual_line_index: int,
    ordinal: int,
) -> PromptReorderPlacementId:
    """Return one stable placement identity for a typed reorder target."""

    if isinstance(target, PromptLineDropTarget):
        return PromptReorderPlacementId(
            target_kind=type(target).__name__,
            row_index=target.row_index,
            insertion_index=target.insertion_index,
            gap_index=None,
            blank_line_index=None,
            visual_line_index=visual_line_index,
            ordinal=ordinal,
        )
    return PromptReorderPlacementId(
        target_kind=type(target).__name__,
        row_index=None,
        insertion_index=None,
        gap_index=target.gap_index,
        blank_line_index=target.blank_line_index,
        visual_line_index=visual_line_index,
        ordinal=ordinal,
    )


def placement_id_context(
    placement_id: PromptReorderPlacementId | None,
    *,
    prefix: str = "placement",
) -> dict[str, object]:
    """Return structured log fields for one placement identity."""

    if placement_id is None:
        return {f"{prefix}_id": "none"}
    return {
        f"{prefix}_target_kind": placement_id.target_kind,
        f"{prefix}_row_index": placement_id.row_index,
        f"{prefix}_insertion_index": placement_id.insertion_index,
        f"{prefix}_gap_index": placement_id.gap_index,
        f"{prefix}_blank_line_index": placement_id.blank_line_index,
        f"{prefix}_visual_line_index": placement_id.visual_line_index,
        f"{prefix}_ordinal": placement_id.ordinal,
    }


def placement_geometry_context(
    placement: PromptReorderPlacementGeometry | None,
    *,
    prefix: str = "placement",
) -> dict[str, object]:
    """Return structured log fields for one placement geometry."""

    if placement is None:
        return {f"{prefix}_id": "none"}
    context: dict[str, object] = {
        **placement_id_context(placement.placement_id, prefix=prefix),
        f"{prefix}_target_kind": reorder_drag_target_kind(placement.target),
        f"{prefix}_source_before": placement.source_before,
        f"{prefix}_source_after": placement.source_after,
        f"{prefix}_adjacent_chip_indices": ",".join(
            str(index) for index in placement.adjacent_chip_indices
        ),
        f"{prefix}_expected_landing_chip_index": placement.expected_landing_chip_index,
    }
    context.update(
        reorder_drag_rect_context(placement.hit_rect, prefix=f"{prefix}_hit")
    )
    context.update(
        reorder_drag_rect_context(
            placement.insertion_anchor_rect,
            prefix=f"{prefix}_anchor",
        )
    )
    context.update(
        reorder_drag_rect_context(
            placement.visual_line_rect,
            prefix=f"{prefix}_visual_line",
        )
    )
    if placement.expected_landing_rect is not None:
        context.update(
            reorder_drag_rect_context(
                placement.expected_landing_rect,
                prefix=f"{prefix}_expected_landing",
            )
        )
    if placement.expected_landing_bounds is not None:
        context.update(
            reorder_drag_rect_context(
                placement.expected_landing_bounds,
                prefix=f"{prefix}_expected_landing_bounds",
            )
        )
    return context


def placement_for_drag_rect(
    snapshot: PromptReorderPlacementSnapshot,
    drag_rect: QRectF,
    *,
    active_placement_id: PromptReorderPlacementId | None,
    gesture_id: int | None = None,
    event_id: int | None = None,
) -> PromptReorderPlacementGeometry | None:
    """Return the projection-owned placement selected by one drag intent rect."""

    started_at = reorder_drag_started_at()
    point = drag_rect.center()
    containing = [
        placement
        for placement in snapshot.placements
        if placement.hit_rect.contains(point)
    ]
    if containing:
        active = _active_placement_from_candidates(containing, active_placement_id)
        if active is not None:
            log_reorder_drag_timing(
                "placement_hit.containing_active",
                started_at=started_at,
                gesture_id=gesture_id,
                event_id=event_id,
                containing_count=len(containing),
                placement_count=len(snapshot.placements),
                **placement_geometry_context(active),
                **reorder_drag_point_context(point, prefix="intent_center"),
            )
            return active
        selected = containing[0]
        log_reorder_drag_timing(
            "placement_hit.containing_first",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            containing_count=len(containing),
            placement_count=len(snapshot.placements),
            **placement_geometry_context(selected),
            **reorder_drag_point_context(point, prefix="intent_center"),
        )
        return selected

    best_line_index = _nearest_visual_line_index(snapshot, point.y())
    if best_line_index is None:
        log_reorder_drag_timing(
            "placement_hit.none",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            placement_count=len(snapshot.placements),
            **reorder_drag_point_context(point, prefix="intent_center"),
        )
        return None

    line_placements = [
        placement
        for placement in snapshot.placements
        if placement.placement_id.visual_line_index == best_line_index
    ]
    nearest = _nearest_anchor_placement(line_placements, point.x())
    log_reorder_drag_timing(
        "placement_hit.nearest_anchor",
        started_at=started_at,
        gesture_id=gesture_id,
        event_id=event_id,
        visual_line_index=best_line_index,
        line_placement_count=len(line_placements),
        placement_count=len(snapshot.placements),
        **placement_geometry_context(nearest),
        **reorder_drag_point_context(point, prefix="intent_center"),
    )
    return nearest


def _active_placement_from_candidates(
    placements: list[PromptReorderPlacementGeometry],
    active_placement_id: PromptReorderPlacementId | None,
) -> PromptReorderPlacementGeometry | None:
    """Return the active placement when it is one of the supplied candidates."""

    if active_placement_id is None:
        return None
    for placement in placements:
        if placement.placement_id == active_placement_id:
            return placement
    return None


def _nearest_visual_line_index(
    snapshot: PromptReorderPlacementSnapshot,
    y_position: float,
) -> int | None:
    """Return the visual line index nearest to the supplied Y coordinate."""

    best_line_index: int | None = None
    best_distance: float | None = None
    seen_lines: set[int] = set()
    for placement in snapshot.placements:
        line_index = placement.placement_id.visual_line_index
        if line_index in seen_lines:
            continue
        seen_lines.add(line_index)
        line_rect = placement.visual_line_rect
        distance = _axis_distance(
            axis_value=y_position,
            start=line_rect.top(),
            end=line_rect.bottom(),
        )
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_line_index = line_index
    return best_line_index


def _nearest_anchor_placement(
    placements: list[PromptReorderPlacementGeometry],
    x_position: float,
) -> PromptReorderPlacementGeometry | None:
    """Return the placement with the nearest insertion anchor X coordinate."""

    best_placement: PromptReorderPlacementGeometry | None = None
    best_distance: float | None = None
    for placement in placements:
        distance = abs(placement.insertion_anchor_rect.center().x() - x_position)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_placement = placement
    return best_placement


def _axis_distance(*, axis_value: float, start: float, end: float) -> float:
    """Return the distance from a scalar point to an inclusive interval."""

    if axis_value < start:
        return start - axis_value
    if axis_value > end:
        return axis_value - end
    return 0.0


def rect_from_centerline(
    *, x: float, y: float, height: float, width: float = 1.0
) -> QRectF:
    """Return a thin rect centered on an insertion anchor line."""

    return QRectF(
        QPointF(x - (width / 2.0), y - (height / 2.0)),
        QSizeF(max(1.0, width), max(1.0, height)),
    )


__all__ = [
    "PromptReorderPlacementGeometry",
    "PromptReorderPlacementId",
    "PromptReorderPlacementSnapshot",
    "duplicate_reorder_placement_targets",
    "placement_for_drag_rect",
    "placement_geometry_context",
    "placement_id_context",
    "rect_from_centerline",
    "reorder_placement_id_for_target",
]
