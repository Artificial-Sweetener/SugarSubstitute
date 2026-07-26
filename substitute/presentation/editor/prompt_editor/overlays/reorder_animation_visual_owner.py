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

"""Publish one coherent displacement and held-chip animation frame."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QWidget

from ..projection.reorder_animation import PromptReorderAnimationPlan
from .reorder_animation_presenter import PromptReorderAnimationPresenter
from .reorder_held_chip_presenter import PromptReorderHeldChipPresenter

_EMPTY_RECTS: Mapping[int, QRectF] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class PromptReorderHeldChipAnimationTarget:
    """Describe one keyboard-held chip animation owned by a prepared plan."""

    generation: int
    segment_index: int
    start_rect: QRectF
    target_rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptReorderAnimationVisualPublication:
    """Publish exact displacement, held-chip, and combined paint rects."""

    revision: int
    displacement_rects_by_index: Mapping[int, QRectF]
    held_rects_by_index: Mapping[int, QRectF]
    paint_rects_by_index: Mapping[int, QRectF]


class PromptReorderAnimationVisualOwner:
    """Own presenter batching and one immutable animation-frame publication."""

    def __init__(
        self,
        *,
        parent: QWidget,
        frame_callback: Callable[[], None],
    ) -> None:
        """Create focused presenters feeding one coherent frame publication."""

        self._frame_callback = frame_callback
        self._displacement_presenter = PromptReorderAnimationPresenter(
            parent=parent,
            frame_callback=self._handle_presenter_frame,
        )
        self._held_presenter = PromptReorderHeldChipPresenter(
            parent=parent,
            frame_callback=self._handle_presenter_frame,
        )
        self._publication = PromptReorderAnimationVisualPublication(
            revision=0,
            displacement_rects_by_index=_EMPTY_RECTS,
            held_rects_by_index=_EMPTY_RECTS,
            paint_rects_by_index=_EMPTY_RECTS,
        )
        self._batch_depth = 0
        self._frame_pending = False

    @property
    def publication(self) -> PromptReorderAnimationVisualPublication:
        """Return the latest coherent animation-frame publication."""

        return self._publication

    def apply_plan(
        self,
        plan: PromptReorderAnimationPlan,
        *,
        held_target: PromptReorderHeldChipAnimationTarget | None,
    ) -> None:
        """Prime held and displacement presenters before publishing one frame."""

        self._begin_batch()
        try:
            if held_target is not None:
                self._held_presenter.apply_target(
                    generation=held_target.generation,
                    segment_index=held_target.segment_index,
                    start_rect=held_target.start_rect,
                    target_rect=held_target.target_rect,
                )
            self._displacement_presenter.apply_plan(plan)
        finally:
            self._end_batch()

    def cancel(self, *, reason: str) -> None:
        """Cancel both presenters and publish their cleared state once."""

        self._begin_batch()
        try:
            self._displacement_presenter.cancel(reason=reason)
            self._held_presenter.cancel(reason=reason)
        finally:
            self._end_batch()

    def settle(self, *, reason: str) -> None:
        """Settle both presenters and publish their cleared overrides once."""

        self._begin_batch()
        try:
            self._displacement_presenter.settle(reason=reason)
            self._held_presenter.settle(reason=reason)
        finally:
            self._end_batch()

    def counters(self) -> dict[str, int]:
        """Return stable combined presenter diagnostics."""

        return {
            **self._displacement_presenter.counters(),
            **self._held_presenter.counters().as_dict(),
        }

    def set_duration_ms(self, duration_ms: int) -> None:
        """Set both presenter durations through their shared lifecycle owner."""

        self._displacement_presenter.set_duration_ms(duration_ms)
        self._held_presenter.set_duration_ms(duration_ms)

    def _begin_batch(self) -> None:
        """Defer publication until all presenter transitions complete."""

        self._batch_depth += 1

    def _end_batch(self) -> None:
        """Publish one pending frame after the outermost transition."""

        self._batch_depth -= 1
        if self._batch_depth > 0 or not self._frame_pending:
            return
        self._frame_pending = False
        self._publish_frame()

    def _handle_presenter_frame(self) -> None:
        """Coalesce presenter callbacks into one immutable frame."""

        if self._batch_depth > 0:
            self._frame_pending = True
            return
        self._publish_frame()

    def _publish_frame(self) -> None:
        """Snapshot both presenter outputs and notify the outer adapter."""

        displacement = self._displacement_presenter.paint_rect_overrides()
        held = self._held_presenter.paint_rect_overrides()
        combined = dict(displacement)
        combined.update(held)
        self._publication = PromptReorderAnimationVisualPublication(
            revision=self._publication.revision + 1,
            displacement_rects_by_index=MappingProxyType(displacement),
            held_rects_by_index=MappingProxyType(held),
            paint_rects_by_index=MappingProxyType(combined),
        )
        self._frame_callback()


__all__ = [
    "PromptReorderAnimationVisualOwner",
    "PromptReorderAnimationVisualPublication",
    "PromptReorderHeldChipAnimationTarget",
]
