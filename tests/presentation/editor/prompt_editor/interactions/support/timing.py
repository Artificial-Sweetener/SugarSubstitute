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

"""Provide deterministic signal and timer doubles for interaction tests."""

from __future__ import annotations

from collections.abc import Callable


class SignalDouble:
    """Store and invoke one callback for signal-like test seams."""

    def __init__(self) -> None:
        """Initialize an empty callback slot."""

        self._callback: Callable[[], None] | None = None

    def connect(self, callback: Callable[[], None]) -> None:
        """Store one callback for later emission."""

        self._callback = callback

    def emit(self) -> None:
        """Invoke the stored callback."""

        assert self._callback is not None
        self._callback()


class FakeTimeoutSignal:
    """Store and invoke one timer callback for deterministic scheduler tests."""

    def __init__(self) -> None:
        """Initialize the fake timeout signal without subscribers."""

        self._callback: Callable[[], None] | None = None

    def connect(self, callback: Callable[[], None]) -> None:
        """Store the callback connected by the production code."""

        self._callback = callback

    def emit(self) -> None:
        """Invoke the connected callback when one exists."""

        assert self._callback is not None
        self._callback()


class FakeQTimer:
    """Provide a deterministic single-shot timer for reorder scheduler tests."""

    instances: list["FakeQTimer"] = []
    single_shots: list[tuple[int, Callable[[], None]]] = []

    def __init__(self) -> None:
        """Track construction and initialize timer state."""

        self.single_shot = False
        self.interval = 0
        self.active = False
        self.started_intervals: list[int] = []
        self.stop_calls = 0
        self.timeout = FakeTimeoutSignal()
        self.__class__.instances.append(self)

    @classmethod
    def singleShot(cls, interval: int, callback: Callable[[], None]) -> None:  # noqa: N802
        """Record one static single-shot callback for manual firing."""

        cls.single_shots.append((interval, callback))

    def setSingleShot(self, single_shot: bool) -> None:  # noqa: N802
        """Record the requested single-shot behavior."""

        self.single_shot = single_shot

    def setInterval(self, interval: int) -> None:  # noqa: N802
        """Record the interval configured before timer starts."""

        self.interval = interval

    def start(self, interval: int) -> None:
        """Record each requested start interval."""

        self.active = True
        self.started_intervals.append(interval)

    def stop(self) -> None:
        """Record timer cancellation requests."""

        self.active = False
        self.stop_calls += 1

    def isActive(self) -> bool:  # noqa: N802
        """Return whether the fake timer is currently active."""

        return self.active

    def fire(self) -> None:
        """Trigger the connected timeout callback immediately."""

        self.active = False
        self.timeout.emit()
