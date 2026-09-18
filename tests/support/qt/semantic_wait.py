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

"""Synchronize Qt tests with semantic state and signal delivery."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtTest import QSignalSpy
from shiboken6 import delete, isValid


def wait_for_qt_condition(
    condition: Callable[[], bool],
    *,
    timeout_ms: int = 3000,
    description: str = "semantic Qt condition",
    state: Callable[[], object] | None = None,
) -> None:
    """Run Qt delivery and distinguish deadline expiration from interrupted delivery."""

    if condition():
        return
    event_loop = QEventLoop()
    observation_timer = QTimer()
    observation_timer.setInterval(1)
    failure_timeout = QTimer()
    failure_timeout.setSingleShot(True)
    expired = False

    def finish_when_observed() -> None:
        """Stop delivery as soon as the authoritative state is visible."""

        if condition():
            event_loop.quit()

    def finish_at_deadline() -> None:
        """Record actual deadline delivery before ending the nested event loop."""
        nonlocal expired
        expired = True
        event_loop.quit()

    observation_timer.timeout.connect(finish_when_observed)
    failure_timeout.timeout.connect(finish_at_deadline)
    try:
        observation_timer.start()
        failure_timeout.start(timeout_ms)
        event_loop.exec()
        observed = condition()
    finally:
        observation_timer.stop()
        failure_timeout.stop()
        observation_timer.timeout.disconnect(finish_when_observed)
        failure_timeout.timeout.disconnect(finish_at_deadline)
        for qt_object in (observation_timer, failure_timeout, event_loop):
            if isValid(qt_object):
                delete(qt_object)
    if observed:
        return
    state_detail = "" if state is None else f"; state={state()!r}"
    if not expired:
        raise AssertionError(f"Qt event loop exited before {description}{state_detail}")
    raise AssertionError(
        f"Timed out after {timeout_ms} ms waiting for {description}{state_detail}"
    )


def wait_for_qt_signal(spy: QSignalSpy, *, timeout_ms: int = 3000) -> None:
    """Wait for at least one observed signal without a check-then-wait race."""

    wait_for_qt_condition(lambda: spy.count() > 0, timeout_ms=timeout_ms)


def wait_for_queued_qt_turn(*, timeout_ms: int = 3000) -> None:
    """Wait until Qt has dispatched callbacks queued before this barrier."""

    reached = False

    def mark_reached() -> None:
        """Publish that the queued barrier callback was dispatched."""

        nonlocal reached
        reached = True

    QTimer.singleShot(0, mark_reached)
    wait_for_qt_condition(lambda: reached, timeout_ms=timeout_ms)


__all__ = [
    "wait_for_qt_condition",
    "wait_for_qt_signal",
    "wait_for_queued_qt_turn",
]
