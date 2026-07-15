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

"""Calculate pending-only generation queue reorder targets."""

from __future__ import annotations

from dataclasses import dataclass

DROP_AFTER_LAST_TOLERANCE = 48


@dataclass(frozen=True)
class PendingRowGeometry:
    """Describe one visible pending row for reorder target calculations."""

    job_id: str
    pending_index: int
    top: int
    bottom: int

    @property
    def height(self) -> int:
        """Return the row height represented by this geometry."""

        return max(0, self.bottom - self.top)


@dataclass(frozen=True)
class PendingDropSlot:
    """Describe one pending insertion slot and its visual y coordinate."""

    insertion_index: int
    y: int


def pending_drop_insertion_index_for_y(
    geometries: tuple[PendingRowGeometry, ...],
    y_position: int,
) -> int | None:
    """Return the pending insertion index for a pointer y position."""

    if y_position < 0 or not geometries:
        return None
    if y_position < geometries[0].top:
        return 0
    for geometry in geometries:
        midpoint = geometry.top + ((geometry.bottom - geometry.top) // 2)
        if y_position < midpoint:
            return geometry.pending_index
    if y_position <= geometries[-1].bottom + DROP_AFTER_LAST_TOLERANCE:
        return len(geometries)
    return None


def pending_drop_slot_for_insertion(
    geometries: tuple[PendingRowGeometry, ...],
    insertion_index: int,
) -> PendingDropSlot | None:
    """Return a visual pending drop slot for an insertion index."""

    if not geometries:
        return None
    if insertion_index <= 0:
        return PendingDropSlot(insertion_index=0, y=geometries[0].top)
    if insertion_index >= len(geometries):
        return PendingDropSlot(
            insertion_index=len(geometries),
            y=geometries[-1].bottom,
        )
    for geometry in geometries:
        if geometry.pending_index == insertion_index:
            return PendingDropSlot(insertion_index=insertion_index, y=geometry.top)
    return None


def service_target_index_for_drop(
    *,
    source_pending_index: int,
    insertion_index: int,
    pending_count: int,
) -> int | None:
    """Return the queue service target index for a dispatch insertion drop."""

    if pending_count <= 0:
        return None
    bounded_insertion = max(0, min(insertion_index, pending_count))
    target_index = bounded_insertion
    if source_pending_index < bounded_insertion:
        target_index -= 1
    target_index = max(0, min(target_index, pending_count - 1))
    if target_index == source_pending_index:
        return None
    return target_index


def dispatch_insertion_index_from_visual(
    visual_insertion_index: int,
    pending_count: int,
) -> int:
    """Return the dispatch insertion slot for a visual pending drop slot."""

    bounded_visual_index = max(0, min(visual_insertion_index, pending_count))
    return pending_count - bounded_visual_index


__all__ = [
    "DROP_AFTER_LAST_TOLERANCE",
    "PendingDropSlot",
    "PendingRowGeometry",
    "dispatch_insertion_index_from_visual",
    "pending_drop_insertion_index_for_y",
    "pending_drop_slot_for_insertion",
    "service_target_index_for_drop",
]
