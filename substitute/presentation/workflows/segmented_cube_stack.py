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

"""Constrain Cube-stack dragging to graph-reorderable topology segments."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from substitute.presentation.workflows.cube_stack_view import CubeStack


class CubeStackReorderBoundaryPolicy:
    """Resolve drag targets without crossing configured Cube graph boundaries."""

    def __init__(self) -> None:
        """Start with unrestricted legacy stack movement."""

        self._segments: tuple[frozenset[str], ...] | None = None

    def configure(self, segments: Iterable[Iterable[str]]) -> None:
        """Set the exact alias groups within which drag movement is allowed."""

        self._segments = tuple(
            frozenset(segment) for segment in segments if frozenset(segment)
        )

    def allowed_target_index(
        self,
        route_keys: Sequence[str],
        current_index: int,
        target_index: int,
    ) -> int:
        """Clamp a requested target to its owning reorderable segment."""

        if self._segments is None:
            return target_index
        if not 0 <= current_index < len(route_keys):
            return current_index
        current_key = route_keys[current_index]
        segment = next(
            (candidate for candidate in self._segments if current_key in candidate),
            None,
        )
        if segment is None or len(segment) < 2:
            return current_index
        segment_indices = [
            index for index, route_key in enumerate(route_keys) if route_key in segment
        ]
        if len(segment_indices) != len(segment):
            return current_index
        return min(max(target_index, min(segment_indices)), max(segment_indices))


class SegmentedCubeStack(CubeStack):
    """Display one stack while enforcing graph-owned reorder boundaries."""

    def __init__(self, parent: object | None = None) -> None:
        """Create a Cube stack with an isolated reorder-boundary policy."""

        super().__init__(parent)
        self._reorder_boundary_policy = CubeStackReorderBoundaryPolicy()

    def setReorderSegments(self, segments: Iterable[Iterable[str]]) -> None:
        """Configure graph segments that may be reordered internally."""

        self._reorder_boundary_policy.configure(segments)

    def _constrain_drag_target_index(self, index: int, target_index: int) -> int:
        """Keep one drag inside its authoritative graph segment."""

        return self._reorder_boundary_policy.allowed_target_index(
            tuple(str(item.routeKey()) for item in self.items),
            index,
            target_index,
        )


__all__ = ["CubeStackReorderBoundaryPolicy", "SegmentedCubeStack"]
