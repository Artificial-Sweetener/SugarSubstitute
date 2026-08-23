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

"""Test Comfy prompt lifecycle event routing."""

from __future__ import annotations

from substitute.infrastructure.comfy.prompt_lifecycle_event_router import (
    route_prompt_lifecycle_event,
)


class _TimingRecorder:
    """Record prompt timing calls emitted by lifecycle routing."""

    def __init__(self) -> None:
        """Initialize an empty call list."""

        self.calls: list[tuple[str, float | None]] = []

    def mark_prompt_started(self, timestamp_ms: float | None) -> None:
        """Record a prompt start call."""

        self.calls.append(("started", timestamp_ms))

    def mark_prompt_terminal(self, timestamp_ms: float | None) -> None:
        """Record a prompt terminal call."""

        self.calls.append(("terminal", timestamp_ms))


def test_route_prompt_lifecycle_event_marks_prompt_start() -> None:
    """execution_start should mark the active prompt as started."""

    timing_tracker = _TimingRecorder()

    result = route_prompt_lifecycle_event(
        "execution_start",
        {"prompt_id": "pid-1", "timestamp": 125.5},
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
    )

    assert result.handled is True
    assert result.interrupted is False
    assert timing_tracker.calls == [("started", 125.5)]


def test_route_prompt_lifecycle_event_marks_prompt_success() -> None:
    """execution_success should mark the active prompt as terminal."""

    timing_tracker = _TimingRecorder()

    result = route_prompt_lifecycle_event(
        "execution_success",
        {"prompt_id": "pid-1", "timestamp": 300},
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
    )

    assert result.handled is True
    assert result.interrupted is False
    assert timing_tracker.calls == [("terminal", 300.0)]


def test_route_prompt_lifecycle_event_reports_interruption() -> None:
    """execution_interrupted should mark terminal timing and request failure."""

    timing_tracker = _TimingRecorder()

    result = route_prompt_lifecycle_event(
        "execution_interrupted",
        {"prompt_id": "pid-1", "timestamp": "missing"},
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
    )

    assert result.handled is True
    assert result.interrupted is True
    assert timing_tracker.calls == [("terminal", None)]


def test_route_prompt_lifecycle_event_ignores_other_prompt_ids() -> None:
    """Lifecycle events for other prompts should be consumed without timing."""

    timing_tracker = _TimingRecorder()

    result = route_prompt_lifecycle_event(
        "execution_success",
        {"prompt_id": "other", "timestamp": 100},
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
    )

    assert result.handled is True
    assert result.interrupted is False
    assert timing_tracker.calls == []


def test_route_prompt_lifecycle_event_ignores_unknown_event_types() -> None:
    """Non-lifecycle events should be left for later routing."""

    timing_tracker = _TimingRecorder()

    result = route_prompt_lifecycle_event(
        "progress",
        {"prompt_id": "pid-1", "timestamp": 100},
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
    )

    assert result.handled is False
    assert result.interrupted is False
    assert timing_tracker.calls == []
