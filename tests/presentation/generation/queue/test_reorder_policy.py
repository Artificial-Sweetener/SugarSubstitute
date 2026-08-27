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

"""Verify pure pending-queue reorder policy."""

from __future__ import annotations

from substitute.presentation.generation.queue_reorder_controller import (
    PendingRowGeometry,
    dispatch_insertion_index_from_visual,
    pending_drop_insertion_index_for_y,
    service_target_index_for_drop,
)


def test_queue_drag_target_calculation_uses_pending_section_only() -> None:
    """Drag target math should use visible pending rows only."""

    geometries = (
        PendingRowGeometry("a", 0, 46, 86),
        PendingRowGeometry("b", 1, 160, 200),
    )

    assert (
        pending_drop_insertion_index_for_y(
            geometries,
            20,
        )
        == 0
    )
    assert (
        pending_drop_insertion_index_for_y(
            geometries,
            80,
        )
        == 1
    )
    assert (
        pending_drop_insertion_index_for_y(
            geometries,
            190,
        )
        == 2
    )
    assert (
        pending_drop_insertion_index_for_y(
            geometries,
            280,
        )
        is None
    )


def test_queue_drag_service_target_suppresses_noop_drops() -> None:
    """Dispatch insertion positions should convert to service target indexes."""

    assert (
        service_target_index_for_drop(
            source_pending_index=2,
            insertion_index=0,
            pending_count=3,
        )
        == 0
    )
    assert (
        service_target_index_for_drop(
            source_pending_index=0,
            insertion_index=3,
            pending_count=3,
        )
        == 2
    )
    assert (
        service_target_index_for_drop(
            source_pending_index=1,
            insertion_index=1,
            pending_count=3,
        )
        is None
    )
    assert (
        service_target_index_for_drop(
            source_pending_index=1,
            insertion_index=2,
            pending_count=3,
        )
        is None
    )


def test_queue_drag_converts_visual_slots_to_dispatch_slots() -> None:
    """Visual bottom-to-top drop slots should become dispatch insertion slots."""

    assert dispatch_insertion_index_from_visual(0, 3) == 3
    assert dispatch_insertion_index_from_visual(1, 3) == 2
    assert dispatch_insertion_index_from_visual(2, 3) == 1
    assert dispatch_insertion_index_from_visual(3, 3) == 0
    assert dispatch_insertion_index_from_visual(-1, 3) == 3
    assert dispatch_insertion_index_from_visual(4, 3) == 0

    top_visual_source_dispatch_index = 2
    bottom_visual_insertion_index = 3
    assert (
        service_target_index_for_drop(
            source_pending_index=top_visual_source_dispatch_index,
            insertion_index=dispatch_insertion_index_from_visual(
                bottom_visual_insertion_index,
                3,
            ),
            pending_count=3,
        )
        == 0
    )

    bottom_visual_source_dispatch_index = 0
    top_visual_insertion_index = 0
    assert (
        service_target_index_for_drop(
            source_pending_index=bottom_visual_source_dispatch_index,
            insertion_index=dispatch_insertion_index_from_visual(
                top_visual_insertion_index,
                3,
            ),
            pending_count=3,
        )
        == 2
    )


def test_queue_drag_target_math_ignores_non_pending_rows() -> None:
    """Pending geometry alone should determine legal drop slots."""

    geometries = (
        PendingRowGeometry("pending-a", 0, 10, 50),
        PendingRowGeometry("pending-b", 1, 60, 100),
    )

    assert pending_drop_insertion_index_for_y(geometries, 120) == 2
    assert pending_drop_insertion_index_for_y(geometries, 180) is None
    assert (
        service_target_index_for_drop(
            source_pending_index=0,
            insertion_index=2,
            pending_count=2,
        )
        == 1
    )
