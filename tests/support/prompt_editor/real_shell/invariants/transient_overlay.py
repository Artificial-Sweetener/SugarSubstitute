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

"""Validate transient deletion overlays captured from a real prompt-editor shell."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.prompt_editor.real_shell.models import (
        PromptEditorStateSnapshot,
        PromptEditorVisibleTextFragment,
    )


class DeletionOverlaySnapshot(Protocol):
    """Expose the exact deletion-overlay state required for overerase checks."""

    @property
    def transient_deletion_overlay_source_range(self) -> tuple[int, int] | None:
        """Return the source range covered by the deletion overlay."""

    @property
    def transient_deletion_overlay_valid(self) -> bool:
        """Return whether the deletion overlay geometry is current."""

    @property
    def transient_deletion_overlay_erase_rects(
        self,
    ) -> tuple[tuple[float, float, float, float], ...]:
        """Return viewport-local erase rectangles owned by the overlay."""

    @property
    def visible_text_fragments(self) -> tuple[PromptEditorVisibleTextFragment, ...]:
        """Return visible fragments used to detect unrelated damage."""


def deletion_overerase_violations(
    snapshot: DeletionOverlaySnapshot,
) -> tuple[str, ...]:
    """Return deletion erase bands that damage unrelated visible text."""

    source_range = snapshot.transient_deletion_overlay_source_range
    if (
        source_range is None
        or not snapshot.transient_deletion_overlay_valid
        or not snapshot.transient_deletion_overlay_erase_rects
    ):
        return ()
    affected_fragments = tuple(
        fragment
        for fragment in snapshot.visible_text_fragments
        if _ranges_overlap(source_range, (fragment.source_start, fragment.source_end))
    )
    if not affected_fragments:
        return ()
    left_bound = min(fragment.viewport_rect[0] for fragment in affected_fragments)
    violations: list[str] = []
    for erase_rect in snapshot.transient_deletion_overlay_erase_rects:
        if erase_rect[0] < left_bound - 3.0:
            violations.append(
                "transient_deletion_overerase_left:"
                f"{erase_rect[0]:.3f}:{left_bound:.3f}"
            )
        for fragment in snapshot.visible_text_fragments:
            if _ranges_overlap(
                source_range, (fragment.source_start, fragment.source_end)
            ):
                continue
            if _rectangles_intersect(erase_rect, fragment.viewport_rect):
                violations.append(
                    f"transient_deletion_overerase_neighbor:{fragment.fragment_index}"
                )
                break
    return tuple(violations)


def violations(snapshot: PromptEditorStateSnapshot) -> tuple[str, ...]:
    """Return invalid transient overlay state and dirty-geometry diagnostics."""

    source_length = len(snapshot.source_text)
    violations: list[str] = []
    if (
        snapshot.transient_caret_geometry_present
        and not snapshot.transient_caret_geometry_valid
    ):
        violations.append("stale_transient_caret_geometry")
    if (
        snapshot.transient_insertion_overlay_present
        and not snapshot.transient_insertion_overlay_valid
    ):
        violations.append("stale_transient_insertion_overlay")
    if snapshot.transient_insertion_overlay_source_range is not None:
        start, end = snapshot.transient_insertion_overlay_source_range
        if not 0 <= start <= end <= source_length:
            violations.append(
                f"transient_insertion_overlay_range_out_of_bounds:{start}:{end}:{source_length}"
            )
    if (
        snapshot.transient_insertion_overlay_present
        and snapshot.transient_insertion_overlay_valid
    ):
        if snapshot.transient_insertion_overlay_viewport_rect is None:
            violations.append("transient_insertion_overlay_viewport_rect_missing")
        if snapshot.transient_insertion_overlay_repaint_rect is None:
            violations.append("transient_insertion_overlay_repaint_rect_missing")
    _extend_dirty_rectangle_violations(
        violations,
        snapshot=snapshot,
        rectangles=(
            (
                "transient_insertion_overlay_viewport_rect",
                snapshot.transient_insertion_overlay_viewport_rect,
            ),
            (
                "transient_insertion_overlay_repaint_rect",
                snapshot.transient_insertion_overlay_repaint_rect,
            ),
        ),
    )
    if (
        snapshot.transient_deletion_overlay_present
        and not snapshot.transient_deletion_overlay_valid
    ):
        violations.append("stale_transient_deletion_overlay")
    if snapshot.transient_deletion_overlay_source_range is not None:
        start, end = snapshot.transient_deletion_overlay_source_range
        if not 0 <= start <= end:
            violations.append(f"transient_deletion_overlay_range_invalid:{start}:{end}")
    if (
        snapshot.transient_deletion_overlay_present
        and snapshot.transient_deletion_overlay_valid
    ):
        if not snapshot.transient_deletion_overlay_viewport_rects:
            violations.append("transient_deletion_overlay_viewport_rects_missing")
        if not snapshot.transient_deletion_overlay_erase_rects:
            violations.append("transient_deletion_overlay_erase_rects_missing")
        if snapshot.transient_deletion_overlay_repaint_rect is None:
            violations.append("transient_deletion_overlay_repaint_rect_missing")
    _extend_dirty_rectangle_violations(
        violations,
        snapshot=snapshot,
        rectangles=(
            ("transient_deletion_overlay_viewport_rect", rectangle)
            for rectangle in snapshot.transient_deletion_overlay_viewport_rects
        ),
    )
    _extend_dirty_rectangle_violations(
        violations,
        snapshot=snapshot,
        rectangles=(
            ("transient_deletion_overlay_erase_rect", rectangle)
            for rectangle in snapshot.transient_deletion_overlay_erase_rects
        ),
    )
    repaint_rectangle = snapshot.transient_deletion_overlay_repaint_rect
    if repaint_rectangle is not None:
        if not rectangle_is_finite_nonnegative(repaint_rectangle):
            violations.append(
                f"transient_deletion_overlay_repaint_rect_invalid:{repaint_rectangle}"
            )
        elif not dirty_rectangle_within_viewport(
            repaint_rectangle, snapshot.viewport_rect
        ):
            violations.append(
                f"transient_deletion_overlay_repaint_rect_too_broad:{repaint_rectangle}"
            )
    return tuple(violations)


def rectangle_is_finite_nonnegative(
    rectangle: tuple[float, float, float, float],
) -> bool:
    """Return whether serialized geometry has finite coordinates and dimensions."""

    _, _, width, height = rectangle
    return (
        all(math.isfinite(value) for value in rectangle)
        and width >= 0.0
        and height >= 0.0
    )


def dirty_rectangle_within_viewport(
    rectangle: tuple[float, float, float, float], viewport: tuple[int, int, int, int]
) -> bool:
    """Return whether a transient dirty rectangle fits its viewport envelope."""

    _, _, width, height = rectangle
    _, _, viewport_width, viewport_height = viewport
    return (
        width <= max(0, viewport_width) + 64.0
        and height <= max(0, viewport_height) + 64.0
    )


def _extend_dirty_rectangle_violations(
    violations: list[str],
    *,
    snapshot: PromptEditorStateSnapshot,
    rectangles: Iterable[tuple[str, tuple[float, float, float, float] | None]],
) -> None:
    """Append validity diagnostics for named transient dirty rectangles."""

    for name, rectangle in rectangles:
        if rectangle is None:
            continue
        if not rectangle_is_finite_nonnegative(rectangle):
            violations.append(f"{name}_invalid:{rectangle}")
        elif not dirty_rectangle_within_viewport(rectangle, snapshot.viewport_rect):
            violations.append(f"{name}_too_broad:{rectangle}")


def _ranges_overlap(first: tuple[int, int], second: tuple[int, int]) -> bool:
    """Return whether two half-open source ranges overlap."""

    return first[0] < second[1] and second[0] < first[1]


def _rectangles_intersect(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> bool:
    """Return whether two serialized rectangles intersect with positive area."""

    first_left, first_top, first_width, first_height = first
    second_left, second_top, second_width, second_height = second
    return (
        first_left < second_left + second_width
        and second_left < first_left + first_width
        and first_top < second_top + second_height
        and second_top < first_top + first_height
    )
