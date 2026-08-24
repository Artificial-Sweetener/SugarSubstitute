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

"""Verify shared Qt synchronization against immediate and queued state."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal
from PySide6.QtTest import QSignalSpy
from shiboken6 import isValid

from tests.support.qt import semantic_wait
from tests.support.qt.semantic_wait import (
    wait_for_qt_condition,
    wait_for_qt_signal,
    wait_for_queued_qt_turn,
)


class _SignalOwner(QObject):
    """Expose one observable signal for synchronization tests."""

    changed = Signal()


def test_wait_for_qt_condition_returns_for_existing_state() -> None:
    """Return immediately when authoritative state is already visible."""

    evaluations = 0

    def condition() -> bool:
        """Record the single immediate state evaluation."""

        nonlocal evaluations
        evaluations += 1
        return True

    wait_for_qt_condition(condition)

    assert evaluations == 1


def test_wait_for_qt_condition_delivers_queued_state_change() -> None:
    """Run queued Qt work until it publishes the requested semantic state."""

    state = {"ready": False}
    QTimer.singleShot(0, lambda: state.__setitem__("ready", True))

    wait_for_qt_condition(lambda: state["ready"])

    assert state["ready"] is True


def test_wait_for_qt_condition_uses_timeout_only_as_failure_bound() -> None:
    """Fail when semantic state never arrives instead of treating time as success."""

    with pytest.raises(
        AssertionError,
        match=(
            "Timed out after 10 ms waiting for prompt caret geometry; "
            "state={'position': 4}"
        ),
    ):
        wait_for_qt_condition(
            lambda: False,
            timeout_ms=10,
            description="prompt caret geometry",
            state=lambda: {"position": 4},
        )


def test_wait_for_qt_condition_destroys_native_wait_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Destroy temporary event-loop owners before returning to the test."""

    created: list[QObject] = []

    def create_event_loop() -> QEventLoop:
        """Capture the event loop created by the semantic wait."""

        event_loop = QEventLoop()
        created.append(event_loop)
        return event_loop

    def create_timer() -> QTimer:
        """Capture each timer created by the semantic wait."""

        timer = QTimer()
        created.append(timer)
        return timer

    evaluations = 0

    def condition() -> bool:
        """Become true on the first observation-timer evaluation."""

        nonlocal evaluations
        evaluations += 1
        return evaluations > 1

    monkeypatch.setattr(semantic_wait, "QEventLoop", create_event_loop)
    monkeypatch.setattr(semantic_wait, "QTimer", create_timer)

    wait_for_qt_condition(condition)

    assert len(created) == 3
    assert all(not isValid(qt_object) for qt_object in created)


def test_wait_for_qt_signal_handles_signal_emitted_before_wait() -> None:
    """Accept an already-observed signal without waiting for another emission."""

    owner = _SignalOwner()
    spy = QSignalSpy(owner.changed)
    owner.changed.emit()

    wait_for_qt_signal(spy)

    assert spy.count() == 1


def test_wait_for_qt_signal_delivers_queued_emission() -> None:
    """Run Qt delivery until a queued signal is observed."""

    owner = _SignalOwner()
    spy = QSignalSpy(owner.changed)
    QTimer.singleShot(0, owner.changed.emit)

    wait_for_qt_signal(spy)

    assert spy.count() == 1


def test_queued_turn_waits_for_callbacks_already_in_delivery_order() -> None:
    """Reach the barrier only after callbacks queued before it have run."""

    deliveries: list[str] = []
    QTimer.singleShot(0, lambda: deliveries.append("work"))

    wait_for_queued_qt_turn()

    assert deliveries == ["work"]
