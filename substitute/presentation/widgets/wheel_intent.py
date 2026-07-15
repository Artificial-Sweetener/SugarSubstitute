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

"""Coordinate deliberate wheel intent for dense editor controls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot
from typing import Final

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget


DEFAULT_WHEEL_DWELL_MS: Final[int] = 400
DEFAULT_WHEEL_STABILITY_RADIUS_PX: Final[int] = 6
DEFAULT_WHEEL_GESTURE_IDLE_MS: Final[int] = 250


class WheelIntentTargetKind(Enum):
    """Classify editor targets that can participate in wheel ownership."""

    EDITOR_SCROLL = "editor_scroll"
    PROMPT_SCROLL = "prompt_scroll"
    NUMERIC_ADJUSTMENT = "numeric_adjustment"
    PROMPT_WEIGHT_ADJUSTMENT = "prompt_weight_adjustment"
    PASSIVE = "passive"


@dataclass(frozen=True)
class WheelIntentTarget:
    """Identify one concrete target that may participate in wheel handling."""

    kind: WheelIntentTargetKind
    widget: QWidget | None
    identity: object

    @classmethod
    def editor_scroll(cls) -> WheelIntentTarget:
        """Return the default editor-scroll target."""

        return cls(
            kind=WheelIntentTargetKind.EDITOR_SCROLL,
            widget=None,
            identity=WheelIntentTargetKind.EDITOR_SCROLL,
        )

    @classmethod
    def passive(cls) -> WheelIntentTarget:
        """Return a passive target that never consumes wheel input."""

        return cls(
            kind=WheelIntentTargetKind.PASSIVE,
            widget=None,
            identity=WheelIntentTargetKind.PASSIVE,
        )

    def can_arm(self) -> bool:
        """Return whether dwell can arm this target for wheel ownership."""

        return self.kind not in {
            WheelIntentTargetKind.EDITOR_SCROLL,
            WheelIntentTargetKind.PASSIVE,
        }


class WheelGestureOwner(Enum):
    """Describe the currently latched wheel gesture owner."""

    EDITOR_SCROLL = "editor_scroll"
    CHILD_TARGET = "child_target"


@dataclass(frozen=True)
class _HoverCandidate:
    """Capture one pointer-qualified target being evaluated for dwell."""

    target: WheelIntentTarget
    global_position: QPoint
    started_at_ms: int


class WheelIntentArbiter:
    """Own pointer-dwell arming and wheel gesture latching for editor controls."""

    def __init__(
        self,
        *,
        dwell_ms: int = DEFAULT_WHEEL_DWELL_MS,
        stability_radius_px: int = DEFAULT_WHEEL_STABILITY_RADIUS_PX,
        gesture_idle_ms: int = DEFAULT_WHEEL_GESTURE_IDLE_MS,
    ) -> None:
        """Initialize dwell and gesture thresholds."""

        self._dwell_ms = max(0, int(dwell_ms))
        self._stability_radius_px = max(0, int(stability_radius_px))
        self._gesture_idle_ms = max(0, int(gesture_idle_ms))
        self._hover_candidate: _HoverCandidate | None = None
        self._armed_target: WheelIntentTarget | None = None
        self._active_target: WheelIntentTarget | None = None
        self._latched_target: WheelIntentTarget | None = None
        self._last_wheel_at_ms: int | None = None

    def handle_pointer_move(
        self,
        *,
        global_position: QPoint,
        target: WheelIntentTarget,
        timestamp_ms: int,
    ) -> None:
        """Update dwell state from real pointer movement."""

        if not target.can_arm():
            self.clear_hover()
            return
        if self._latched_target is not None and self._latched_target != target:
            self.clear_gesture()
        if self._armed_target == target:
            self._hover_candidate = _HoverCandidate(
                target=target,
                global_position=QPoint(global_position),
                started_at_ms=timestamp_ms - self._dwell_ms,
            )
            return
        candidate = self._hover_candidate
        if candidate is None or candidate.target != target:
            self._armed_target = None
            self._hover_candidate = _HoverCandidate(
                target=target,
                global_position=QPoint(global_position),
                started_at_ms=timestamp_ms,
            )
            return
        if self._distance_between(candidate.global_position, global_position) > (
            self._stability_radius_px
        ):
            self._armed_target = None
            self._hover_candidate = _HoverCandidate(
                target=target,
                global_position=QPoint(global_position),
                started_at_ms=timestamp_ms,
            )

    def clear_hover(self) -> None:
        """Clear any pointer-dwell candidate and armed target."""

        self._hover_candidate = None
        self._armed_target = None

    def armed_target(self, *, timestamp_ms: int) -> WheelIntentTarget | None:
        """Return the target currently armed by pointer dwell."""

        if self._latched_target is not None:
            return None
        if self._armed_target is not None:
            return self._armed_target
        candidate = self._hover_candidate
        if candidate is None:
            return None
        if timestamp_ms - candidate.started_at_ms < self._dwell_ms:
            return None
        self._armed_target = candidate.target
        return candidate.target

    def target_is_armed(
        self,
        target: WheelIntentTarget,
        *,
        timestamp_ms: int,
    ) -> bool:
        """Return whether one target is currently armed."""

        self.end_gesture_if_idle(timestamp_ms=timestamp_ms)
        return self.armed_target(timestamp_ms=timestamp_ms) == target

    def set_active_target(self, target: WheelIntentTarget) -> None:
        """Remember a target chosen by explicit user activation."""

        if not target.can_arm():
            self._active_target = None
            return
        self._active_target = target

    def clear_active_target(self, target: WheelIntentTarget) -> None:
        """Clear active intent when a specific target loses activation."""

        if self._active_target == target:
            self._active_target = None

    def wheel_owner_for_event(
        self,
        *,
        target: WheelIntentTarget,
        timestamp_ms: int,
        target_can_accept_wheel: bool = True,
    ) -> WheelIntentTarget:
        """Return and latch the target that should own one wheel event."""

        self.end_gesture_if_idle(timestamp_ms=timestamp_ms)
        if self._latched_target is not None:
            if self._latched_target != target:
                self.clear_gesture()
            else:
                if (
                    self._latched_target.kind is WheelIntentTargetKind.PROMPT_SCROLL
                    and not target_can_accept_wheel
                ):
                    self._latched_target = WheelIntentTarget.editor_scroll()
                self._last_wheel_at_ms = timestamp_ms
                return self._latched_target

        active_target = self._active_target
        if (
            active_target is not None
            and active_target == target
            and target_can_accept_wheel
        ):
            self._latched_target = active_target
            self._last_wheel_at_ms = timestamp_ms
            return self._latched_target

        armed_target = self.armed_target(timestamp_ms=timestamp_ms)
        if (
            armed_target is not None
            and armed_target == target
            and target_can_accept_wheel
        ):
            self._latched_target = armed_target
            self._last_wheel_at_ms = timestamp_ms
            return self._latched_target

        if target.can_arm():
            if (
                armed_target is None
                or armed_target != target
                or target_can_accept_wheel
            ):
                self._restart_dwell_for_target(
                    target,
                    timestamp_ms=timestamp_ms,
                )
            return WheelIntentTarget.editor_scroll()

        self._latched_target = WheelIntentTarget.editor_scroll()
        self._last_wheel_at_ms = timestamp_ms
        return self._latched_target

    def _restart_dwell_for_target(
        self,
        target: WheelIntentTarget,
        *,
        timestamp_ms: int,
    ) -> None:
        """Restart dwell for a target after a premature wheel attempt."""

        self._armed_target = None
        candidate = self._hover_candidate
        if candidate is None or candidate.target != target:
            return
        self._hover_candidate = _HoverCandidate(
            target=target,
            global_position=QPoint(candidate.global_position),
            started_at_ms=timestamp_ms,
        )

    def end_gesture_if_idle(self, *, timestamp_ms: int) -> None:
        """Clear latched wheel ownership once the idle timeout expires."""

        if self._last_wheel_at_ms is None:
            return
        if timestamp_ms - self._last_wheel_at_ms >= self._gesture_idle_ms:
            self._latched_target = None
            self._last_wheel_at_ms = None

    def clear_gesture(self) -> None:
        """Clear the current wheel gesture owner."""

        self._latched_target = None
        self._last_wheel_at_ms = None

    @staticmethod
    def _distance_between(first: QPoint, second: QPoint) -> float:
        """Return Euclidean distance between two global pointer positions."""

        return hypot(first.x() - second.x(), first.y() - second.y())


__all__ = [
    "DEFAULT_WHEEL_DWELL_MS",
    "DEFAULT_WHEEL_GESTURE_IDLE_MS",
    "DEFAULT_WHEEL_STABILITY_RADIUS_PX",
    "WheelGestureOwner",
    "WheelIntentArbiter",
    "WheelIntentTarget",
    "WheelIntentTargetKind",
]
