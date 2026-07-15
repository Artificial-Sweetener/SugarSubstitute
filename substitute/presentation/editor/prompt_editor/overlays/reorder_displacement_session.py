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

"""Own reorder displacement state shared by pointer drag and Alt+Arrow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor import PromptReorderDropTarget

from .reorder_displacement_intent import (
    ReorderDisplacementInputSource,
    ReorderDisplacementIntent,
)


@dataclass(frozen=True, slots=True)
class ReorderDisplacementPendingTarget:
    """Describe one target change ready for settled preview geometry."""

    generation: int
    target: PromptReorderDropTarget
    reason: str
    held_segment_index: int
    source: ReorderDisplacementInputSource


@dataclass(frozen=True, slots=True)
class ReorderDisplacementSessionState:
    """Expose current display-only displacement state for tests and coordination."""

    active: bool = False
    input_source: ReorderDisplacementInputSource | None = None
    held_segment_index: int | None = None
    active_target: PromptReorderDropTarget | None = None
    previous_visible_rects: Mapping[int, QRectF] = field(default_factory=dict)
    preview_generation: int = 0
    animation_generation: int = 0
    raster_generation: int = 0


class ReorderDisplacementSession:
    """Track active visual displacement without owning layout, paint, or mutation."""

    def __init__(self) -> None:
        """Initialize an inactive displacement session."""

        self._state = ReorderDisplacementSessionState()
        self._pending_target: ReorderDisplacementPendingTarget | None = None

    @property
    def state(self) -> ReorderDisplacementSessionState:
        """Return the current immutable session state."""

        return self._state

    @property
    def pending_target(self) -> ReorderDisplacementPendingTarget | None:
        """Return the target change waiting for preview geometry, if any."""

        return self._pending_target

    def record_target_change(
        self,
        intent: ReorderDisplacementIntent,
        *,
        generation: int,
        previous_visible_rects: Mapping[int, QRectF],
    ) -> ReorderDisplacementPendingTarget | None:
        """Record a target change and return pending animation metadata."""

        copied_rects = {
            segment_index: QRectF(rect)
            for segment_index, rect in previous_visible_rects.items()
        }
        if intent.target is None:
            self.clear(
                preview_generation=self._state.preview_generation,
                animation_generation=generation,
                raster_generation=self._state.raster_generation,
            )
            return None
        pending = ReorderDisplacementPendingTarget(
            generation=generation,
            target=intent.target,
            reason=intent.reason,
            held_segment_index=intent.held_segment_index,
            source=intent.source,
        )
        self._pending_target = pending
        self._state = ReorderDisplacementSessionState(
            active=True,
            input_source=intent.source,
            held_segment_index=intent.held_segment_index,
            active_target=intent.target,
            previous_visible_rects=copied_rects,
            preview_generation=self._state.preview_generation + 1,
            animation_generation=generation,
            raster_generation=self._state.raster_generation,
        )
        return pending

    def consume_pending_target(
        self,
        *,
        active_target: PromptReorderDropTarget | None,
    ) -> ReorderDisplacementPendingTarget | None:
        """Return and clear a pending target only when it still matches."""

        pending = self._pending_target
        self._pending_target = None
        if pending is None or pending.target != active_target:
            return None
        return pending

    def clear(
        self,
        *,
        preview_generation: int | None = None,
        animation_generation: int | None = None,
        raster_generation: int | None = None,
    ) -> None:
        """Reset active displacement state while preserving generation monotonicity."""

        self._pending_target = None
        self._state = ReorderDisplacementSessionState(
            preview_generation=(
                self._state.preview_generation
                if preview_generation is None
                else preview_generation
            ),
            animation_generation=(
                self._state.animation_generation
                if animation_generation is None
                else animation_generation
            ),
            raster_generation=(
                self._state.raster_generation
                if raster_generation is None
                else raster_generation
            ),
        )

    def bump_raster_generation(self) -> int:
        """Advance and return the raster generation for cache invalidation."""

        next_generation = self._state.raster_generation + 1
        self._state = ReorderDisplacementSessionState(
            active=self._state.active,
            input_source=self._state.input_source,
            held_segment_index=self._state.held_segment_index,
            active_target=self._state.active_target,
            previous_visible_rects=self._state.previous_visible_rects,
            preview_generation=self._state.preview_generation,
            animation_generation=self._state.animation_generation,
            raster_generation=next_generation,
        )
        return next_generation


__all__ = [
    "ReorderDisplacementPendingTarget",
    "ReorderDisplacementSession",
    "ReorderDisplacementSessionState",
]
