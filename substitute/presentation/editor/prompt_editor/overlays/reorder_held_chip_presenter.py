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

"""Present the held reorder chip independently from neighbor displacement."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QEasingCurve, QRectF, QVariantAnimation
from PySide6.QtWidgets import QWidget


@dataclass(frozen=True, slots=True)
class PromptReorderHeldChipCounters:
    """Summarize held-chip animation presenter activity."""

    held_animation_started_count: int = 0
    held_animation_finished_count: int = 0
    held_animation_cancelled_count: int = 0
    held_animation_settled_count: int = 0

    def as_dict(self) -> dict[str, int]:
        """Return JSON-safe counters for diagnostics and tests."""

        return {
            "held_animation_started_count": self.held_animation_started_count,
            "held_animation_finished_count": self.held_animation_finished_count,
            "held_animation_cancelled_count": self.held_animation_cancelled_count,
            "held_animation_settled_count": self.held_animation_settled_count,
        }


class PromptReorderHeldChipPresenter:
    """Animate the keyboard-held chip as a paint rect override."""

    def __init__(
        self,
        *,
        parent: QWidget,
        frame_callback: Callable[[], None] | None = None,
        duration_ms: int = 180,
    ) -> None:
        """Initialize held-chip animation state."""

        self._parent = parent
        self._frame_callback = frame_callback
        self._duration_ms = duration_ms
        self._animation: QVariantAnimation | None = None
        self._active_generation: int | None = None
        self._active_segment_index: int | None = None
        self._current_rect: QRectF | None = None
        self._target_rect: QRectF | None = None
        self._started_count = 0
        self._finished_count = 0
        self._cancelled_count = 0
        self._settled_count = 0

    def apply_target(
        self,
        *,
        generation: int,
        segment_index: int,
        start_rect: QRectF,
        target_rect: QRectF,
    ) -> None:
        """Animate the held chip from its previous rect to the settled target rect."""

        self.cancel(reason="generation_replaced")
        self._active_generation = generation
        self._active_segment_index = segment_index
        self._current_rect = QRectF(start_rect)
        self._target_rect = QRectF(target_rect)
        animation = QVariantAnimation(self._parent)
        animation.setStartValue(QRectF(start_rect))
        animation.setEndValue(QRectF(target_rect))
        animation.setDuration(self._duration_ms)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.valueChanged.connect(self._handle_value_changed)
        animation.finished.connect(self._handle_finished)
        self._animation = animation
        self._started_count += 1
        self._notify_frame()
        animation.start()

    def paint_rect_overrides(self) -> dict[int, QRectF]:
        """Return the active held-chip rect override, if any."""

        if self._active_segment_index is None or self._current_rect is None:
            return {}
        return {self._active_segment_index: QRectF(self._current_rect)}

    def settle(self, *, reason: str) -> None:
        """Stop active held motion and publish the target rect."""

        _ = reason
        if self._animation is not None:
            self._animation.stop()
            self._animation.deleteLater()
            self._animation = None
        if self._target_rect is None:
            return
        self._current_rect = QRectF(self._target_rect)
        self._settled_count += 1
        self._clear_active()
        self._notify_frame()

    def cancel(self, *, reason: str) -> None:
        """Stop active held motion without applying the target rect."""

        _ = reason
        if self._animation is None and self._active_segment_index is None:
            return
        if self._animation is not None:
            self._animation.stop()
            self._animation.deleteLater()
            self._animation = None
        self._cancelled_count += 1
        self._clear_active()
        self._notify_frame()

    def counters(self) -> PromptReorderHeldChipCounters:
        """Return current held presenter counters."""

        return PromptReorderHeldChipCounters(
            held_animation_started_count=self._started_count,
            held_animation_finished_count=self._finished_count,
            held_animation_cancelled_count=self._cancelled_count,
            held_animation_settled_count=self._settled_count,
        )

    def _handle_value_changed(self, value: object) -> None:
        """Publish one interpolated held-chip rect."""

        if isinstance(value, QRectF):
            self._current_rect = QRectF(value)
            self._notify_frame()

    def _handle_finished(self) -> None:
        """Clear active state after the held chip reaches its target."""

        if self._target_rect is not None:
            self._current_rect = QRectF(self._target_rect)
        self._finished_count += 1
        if self._animation is not None:
            self._animation.deleteLater()
            self._animation = None
        self._clear_active()
        self._notify_frame()

    def _clear_active(self) -> None:
        """Clear active held identity after settle, cancel, or finish."""

        self._active_generation = None
        self._active_segment_index = None
        self._current_rect = None
        self._target_rect = None

    def _notify_frame(self) -> None:
        """Notify the overlay that held-chip paint overrides changed."""

        if self._frame_callback is not None:
            self._frame_callback()


__all__ = ["PromptReorderHeldChipCounters", "PromptReorderHeldChipPresenter"]
