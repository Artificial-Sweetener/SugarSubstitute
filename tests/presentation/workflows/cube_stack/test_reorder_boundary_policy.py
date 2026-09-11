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

"""Verify Cube-stack drag targets respect ordinary graph boundaries."""

from __future__ import annotations

from substitute.presentation.workflows.segmented_cube_stack import (
    CubeStackReorderBoundaryPolicy,
)


def test_reorderable_segment_clamps_drag_before_adjacent_boundary() -> None:
    """Allow internal movement without entering another graph segment."""

    policy = CubeStackReorderBoundaryPolicy()
    policy.configure((("First", "Second"), ("Third", "Fourth")))
    route_keys = ("First", "Second", "Third", "Fourth")

    assert policy.allowed_target_index(route_keys, 0, 3) == 1
    assert policy.allowed_target_index(route_keys, 3, 0) == 2


def test_fixed_cube_cannot_move_when_no_reorderable_segment_owns_it() -> None:
    """Keep branch, cycle, and singleton Cubes fixed in their graph position."""

    policy = CubeStackReorderBoundaryPolicy()
    policy.configure((("First", "Second"),))

    assert policy.allowed_target_index(("First", "Second", "Fixed"), 2, 0) == 2


def test_legacy_stack_remains_unrestricted_without_graph_segments() -> None:
    """Preserve existing recipe-stack behavior when no graph policy is configured."""

    policy = CubeStackReorderBoundaryPolicy()

    assert policy.allowed_target_index(("First", "Second"), 0, 1) == 1
