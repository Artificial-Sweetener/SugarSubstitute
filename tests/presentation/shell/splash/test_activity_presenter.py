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

"""Prove splash activity behavior without launching a visible window."""

from __future__ import annotations

from sugarsubstitute_shared.launch_splash import SplashActivity
from sugarsubstitute_shared.presentation.terminal import TerminalOutputStream

from substitute.presentation.shell.splash_activity_presenter import (
    SplashActivityPresenter,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _Clock:
    """Expose deterministic monotonic time for activity lifecycle tests."""

    def __init__(self) -> None:
        """Start at the zero epoch."""

        self.now = 0.0

    def __call__(self) -> float:
        """Return the controlled monotonic timestamp."""

        return self.now


class _AdvancingClock:
    """Advance one activity second per scheduled render after startup."""

    def __init__(self) -> None:
        """Initialize the start-time and first-frame calls at zero."""

        self._calls = 0

    def __call__(self) -> float:
        """Return zero twice, then advance once per timer-driven refresh."""

        self._calls += 1
        return float(max(0, self._calls - 2))


def test_silent_activity_animates_without_growing_transcript() -> None:
    """Replace one tail row while silent work advances through every wait stage."""

    clock = _Clock()
    stream = TerminalOutputStream(max_lines=20)
    presenter = SplashActivityPresenter(stream=stream, clock=clock)
    presenter.start(
        SplashActivity(
            initial_text="Updating SugarCubes",
            long_wait_text="Updating SugarCubes is taking longer than usual",
            extended_wait_text="Still updating SugarCubes—network may be slow",
        )
    )

    expected_frames = {
        0.0: "Updating SugarCubes.",
        1.0: "Updating SugarCubes..",
        2.0: "Updating SugarCubes...",
        120.0: "Updating SugarCubes is taking longer than usual.",
        121.0: "Updating SugarCubes is taking longer than usual..",
        122.0: "Updating SugarCubes is taking longer than usual...",
        300.0: "Still updating SugarCubes—network may be slow.",
        301.0: "Still updating SugarCubes—network may be slow..",
        302.0: "Still updating SugarCubes—network may be slow...",
    }
    for elapsed_seconds, expected in expected_frames.items():
        clock.now = elapsed_seconds
        presenter.refresh()
        assert stream.snapshot() == (expected,)

    presenter.shutdown()


def test_activity_timer_schedules_headless_dot_frames() -> None:
    """The real Qt timer should emit successive dot frames without producer output."""

    stream = TerminalOutputStream(max_lines=20)
    frames: list[str] = []
    stream.changed.connect(lambda: frames.append(stream.snapshot()[-1]))
    presenter = SplashActivityPresenter(
        stream=stream,
        clock=_AdvancingClock(),
        frame_interval_milliseconds=1,
    )

    presenter.start(
        SplashActivity(
            initial_text="Waiting for ComfyUI",
            long_wait_text="ComfyUI is taking longer than usual",
            extended_wait_text="Still waiting for ComfyUI",
        )
    )

    wait_for_qt_condition(lambda: len(frames) >= 3)
    presenter.shutdown()

    assert frames[:3] == [
        "Waiting for ComfyUI.",
        "Waiting for ComfyUI..",
        "Waiting for ComfyUI...",
    ]


def test_activity_preserves_logs_and_clears_only_its_tail_row() -> None:
    """Restore active copy after durable output and remove it on completion."""

    clock = _Clock()
    stream = TerminalOutputStream(max_lines=20)
    presenter = SplashActivityPresenter(stream=stream, clock=clock)
    presenter.start(
        SplashActivity(
            initial_text="Installing dependencies",
            long_wait_text="Installing dependencies is taking longer than usual",
            extended_wait_text="Still installing dependencies—network may be slow",
        )
    )

    stream.append_line("Downloaded package metadata\n")
    presenter.restore_after_log("Downloaded package metadata\n")

    assert stream.snapshot() == (
        "Downloaded package metadata",
        "Installing dependencies.",
    )

    presenter.clear()

    assert presenter.active is False
    assert stream.snapshot() == ("Downloaded package metadata",)
