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

"""Plan prompt reorder chip animation from settled projection geometry."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor import PromptReorderLayoutView


PromptReorderAnimationFallbackDisposition = Literal["immediate", "skipped"]

_RECT_MATCH_TOLERANCE = 0.01


@dataclass(frozen=True, slots=True)
class PromptReorderAnimationTarget:
    """Describe one chip rect transition derived from settled reorder geometry."""

    segment_index: int
    start_rect: QRectF
    target_rect: QRectF
    target_visible: bool

    def __post_init__(self) -> None:
        """Store defensive rect copies inside the frozen target value."""

        object.__setattr__(self, "start_rect", QRectF(self.start_rect))
        object.__setattr__(self, "target_rect", QRectF(self.target_rect))


@dataclass(frozen=True, slots=True)
class PromptReorderAnimationFallback:
    """Describe why one chip cannot use animated displacement for a plan."""

    segment_index: int
    disposition: PromptReorderAnimationFallbackDisposition
    reason: str
    generation: int
    has_current_rect: bool
    has_target_rect: bool
    target_visible: bool


@dataclass(frozen=True, slots=True)
class PromptReorderAnimationPlan:
    """Describe one display-only reorder animation plan from settled geometry."""

    generation: int
    dragged_segment_index: int | None
    ordered_segment_indices: tuple[int, ...]
    layout_view: PromptReorderLayoutView
    changed_targets: tuple[PromptReorderAnimationTarget, ...]
    immediate_segment_indices: frozenset[int]
    reason: str
    immediate_targets: tuple[PromptReorderAnimationTarget, ...] = ()
    skipped_segment_indices: frozenset[int] = frozenset()
    fallbacks: tuple[PromptReorderAnimationFallback, ...] = ()
    stale: bool = False


class PromptReorderAnimationPlanner:
    """Build stale-safe animation plans without owning widgets or timers."""

    def __init__(self) -> None:
        """Initialize the generation watermark used to reject stale plans."""

        self._latest_generation = -1

    def build_plan(
        self,
        *,
        generation: int,
        current_visuals: Mapping[int, QRectF],
        proposed_layout_view: PromptReorderLayoutView,
        proposed_chip_geometry: Mapping[int, QRectF],
        ordered_segment_indices: tuple[int, ...],
        dragged_segment_index: int | None,
        reason: str,
    ) -> PromptReorderAnimationPlan:
        """Return displacement targets derived from settled reorder geometry."""

        if generation < self._latest_generation:
            return self._stale_plan(
                generation=generation,
                proposed_layout_view=proposed_layout_view,
                ordered_segment_indices=ordered_segment_indices,
                dragged_segment_index=dragged_segment_index,
                reason=reason,
            )
        self._latest_generation = generation

        changed_targets: list[PromptReorderAnimationTarget] = []
        immediate_targets: list[PromptReorderAnimationTarget] = []
        immediate_segment_indices: set[int] = set()
        skipped_segment_indices: set[int] = set()
        fallbacks: list[PromptReorderAnimationFallback] = []
        layout_segment_indices = _layout_segment_indices(proposed_layout_view)

        for segment_index in ordered_segment_indices:
            if segment_index == dragged_segment_index:
                continue

            current_rect = current_visuals.get(segment_index)
            target_rect = proposed_chip_geometry.get(segment_index)
            target_visible = target_rect is not None and _rect_is_visible(target_rect)

            if target_rect is None:
                skipped_segment_indices.add(segment_index)
                fallbacks.append(
                    PromptReorderAnimationFallback(
                        segment_index=segment_index,
                        disposition="skipped",
                        reason=(
                            "target_rect_missing"
                            if segment_index in layout_segment_indices
                            else "segment_missing_from_settled_layout"
                        ),
                        generation=generation,
                        has_current_rect=current_rect is not None,
                        has_target_rect=False,
                        target_visible=False,
                    )
                )
                continue

            if not target_visible:
                skipped_segment_indices.add(segment_index)
                fallbacks.append(
                    PromptReorderAnimationFallback(
                        segment_index=segment_index,
                        disposition="skipped",
                        reason="target_rect_not_visible",
                        generation=generation,
                        has_current_rect=current_rect is not None,
                        has_target_rect=True,
                        target_visible=False,
                    )
                )
                continue

            if current_rect is None:
                immediate_segment_indices.add(segment_index)
                immediate_targets.append(
                    PromptReorderAnimationTarget(
                        segment_index=segment_index,
                        start_rect=QRectF(target_rect),
                        target_rect=target_rect,
                        target_visible=True,
                    )
                )
                fallbacks.append(
                    PromptReorderAnimationFallback(
                        segment_index=segment_index,
                        disposition="immediate",
                        reason="current_rect_missing",
                        generation=generation,
                        has_current_rect=False,
                        has_target_rect=True,
                        target_visible=True,
                    )
                )
                continue

            if _rects_match(current_rect, target_rect):
                continue

            changed_targets.append(
                PromptReorderAnimationTarget(
                    segment_index=segment_index,
                    start_rect=current_rect,
                    target_rect=target_rect,
                    target_visible=True,
                )
            )

        return PromptReorderAnimationPlan(
            generation=generation,
            dragged_segment_index=dragged_segment_index,
            ordered_segment_indices=ordered_segment_indices,
            layout_view=proposed_layout_view,
            changed_targets=tuple(changed_targets),
            immediate_segment_indices=frozenset(immediate_segment_indices),
            reason=reason,
            immediate_targets=tuple(immediate_targets),
            skipped_segment_indices=frozenset(skipped_segment_indices),
            fallbacks=tuple(fallbacks),
        )

    def _stale_plan(
        self,
        *,
        generation: int,
        proposed_layout_view: PromptReorderLayoutView,
        ordered_segment_indices: tuple[int, ...],
        dragged_segment_index: int | None,
        reason: str,
    ) -> PromptReorderAnimationPlan:
        """Return an inert plan for geometry older than the planner watermark."""

        skipped_segment_indices = frozenset(
            segment_index
            for segment_index in ordered_segment_indices
            if segment_index != dragged_segment_index
        )
        return PromptReorderAnimationPlan(
            generation=generation,
            dragged_segment_index=dragged_segment_index,
            ordered_segment_indices=ordered_segment_indices,
            layout_view=proposed_layout_view,
            changed_targets=(),
            immediate_segment_indices=frozenset(),
            reason=reason,
            skipped_segment_indices=skipped_segment_indices,
            fallbacks=tuple(
                PromptReorderAnimationFallback(
                    segment_index=segment_index,
                    disposition="skipped",
                    reason="stale_generation",
                    generation=generation,
                    has_current_rect=False,
                    has_target_rect=False,
                    target_visible=False,
                )
                for segment_index in skipped_segment_indices
            ),
            stale=True,
        )


def _layout_segment_indices(layout_view: PromptReorderLayoutView) -> frozenset[int]:
    """Return every semantic segment index represented by one settled layout."""

    return frozenset(
        segment_index for row in layout_view.rows for segment_index in row.chip_indices
    )


def _rect_is_visible(rect: QRectF) -> bool:
    """Return whether a settled rect is usable as a visible animation target."""

    return not rect.isNull() and not rect.isEmpty()


def _rects_match(first: QRectF, second: QRectF) -> bool:
    """Return whether two projection rects are visually equivalent."""

    return (
        abs(first.left() - second.left()) <= _RECT_MATCH_TOLERANCE
        and abs(first.top() - second.top()) <= _RECT_MATCH_TOLERANCE
        and abs(first.width() - second.width()) <= _RECT_MATCH_TOLERANCE
        and abs(first.height() - second.height()) <= _RECT_MATCH_TOLERANCE
    )


__all__ = [
    "PromptReorderAnimationFallback",
    "PromptReorderAnimationFallbackDisposition",
    "PromptReorderAnimationPlan",
    "PromptReorderAnimationPlanner",
    "PromptReorderAnimationTarget",
]
