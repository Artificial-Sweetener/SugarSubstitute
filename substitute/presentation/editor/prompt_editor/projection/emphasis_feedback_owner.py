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

"""Own transient emphasis decoration accent feedback."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer

_DEFAULT_PULSE_DURATION_MS = 220


class PromptProjectionEmphasisFeedbackOwner(QObject):
    """Coordinate persistent interaction accents and one bounded feedback pulse."""

    def __init__(
        self,
        *,
        is_projected: Callable[[], bool],
        apply_paint_state: Callable[[], None],
        parent: QObject,
        pulse_duration_ms: int = _DEFAULT_PULSE_DURATION_MS,
    ) -> None:
        """Bind accent state to projection eligibility and paint publication."""

        super().__init__(parent)
        self._is_projected = is_projected
        self._apply_paint_state = apply_paint_state
        self._overlay_range: tuple[int, int] | None = None
        self._wheel_intent_range: tuple[int, int] | None = None
        self._pulsed_range: tuple[int, int] | None = None
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setSingleShot(True)
        self._pulse_timer.setInterval(pulse_duration_ms)
        self._pulse_timer.timeout.connect(self.clear_pulse)

    def set_overlay_range(self, outer_range: tuple[int, int] | None) -> None:
        """Publish the accent range owned by visible weight controls."""

        if outer_range == self._overlay_range:
            return
        self._overlay_range = outer_range
        self._apply_if_projected()

    def set_wheel_intent_range(self, outer_range: tuple[int, int] | None) -> None:
        """Publish the accent range owned by wheel-intent dwell."""

        if outer_range == self._wheel_intent_range:
            return
        self._wheel_intent_range = outer_range
        self._apply_if_projected()

    def pulse(self, outer_range: tuple[int, int]) -> None:
        """Accent one emphasis shell until the bounded feedback pulse expires."""

        self._pulsed_range = outer_range
        self._pulse_timer.start()
        self._apply_if_projected()

    def clear_pulse(self) -> None:
        """Clear a completed pulse and publish the remaining accent state."""

        if self._pulsed_range is None:
            return
        self._pulsed_range = None
        self._apply_if_projected()

    def accent_ranges(self) -> tuple[tuple[int, int], ...]:
        """Return unique accent ranges in stable interaction-priority order."""

        ranges: list[tuple[int, int]] = []
        for outer_range in (
            self._overlay_range,
            self._wheel_intent_range,
            self._pulsed_range,
        ):
            if outer_range is not None and outer_range not in ranges:
                ranges.append(outer_range)
        return tuple(ranges)

    def _apply_if_projected(self) -> None:
        """Publish accent paint only while decorated projection is visible."""

        if self._is_projected():
            self._apply_paint_state()


__all__ = ["PromptProjectionEmphasisFeedbackOwner"]
