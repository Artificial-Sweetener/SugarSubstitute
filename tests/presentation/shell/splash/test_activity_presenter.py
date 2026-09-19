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

from collections.abc import Callable

from PySide6.QtCore import QObject

from sugarsubstitute_shared.launch_splash import SplashActivity
from sugarsubstitute_shared.presentation.terminal import TerminalOutputStream

from substitute.presentation.shell.splash_activity_presenter import (
    SplashActivityPresenter,
)


class _Clock:
    """Expose deterministic monotonic time for activity lifecycle tests."""

    def __init__(self) -> None:
        """Start at the zero epoch."""

        self.now = 0.0

    def __call__(self) -> float:
        """Return the controlled monotonic timestamp."""

        return self.now


class _ManualFrameScheduler:
    """Deliver frame callbacks only when the test requests a frame."""

    def __init__(self, callback: Callable[[], None]) -> None:
        """Capture the callback without consulting a wall clock."""

        self._callback = callback
        self._active = False

    def start(self) -> None:
        """Permit requested frame delivery."""

        self._active = True

    def stop(self) -> None:
        """Prevent further requested frame delivery."""

        self._active = False

    def deliver_frame(self) -> None:
        """Deliver one scheduled frame when active."""

        if self._active:
            self._callback()


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


def test_activity_scheduler_delivers_headless_dot_frames() -> None:
    """Scheduled callbacks should advance frames without producer output."""

    clock = _Clock()
    stream = TerminalOutputStream(max_lines=20)
    frames: list[str] = []
    scheduler: _ManualFrameScheduler | None = None

    def create_scheduler(
        _parent: QObject,
        _interval_milliseconds: int,
        callback: Callable[[], None],
    ) -> _ManualFrameScheduler:
        """Capture the presenter scheduler for deterministic delivery."""

        nonlocal scheduler
        scheduler = _ManualFrameScheduler(callback)
        return scheduler

    stream.changed.connect(lambda: frames.append(stream.snapshot()[-1]))
    presenter = SplashActivityPresenter(
        stream=stream,
        clock=clock,
        frame_interval_milliseconds=1,
        scheduler_factory=create_scheduler,
    )

    presenter.start(
        SplashActivity(
            initial_text="Waiting for ComfyUI",
            long_wait_text="ComfyUI is taking longer than usual",
            extended_wait_text="Still waiting for ComfyUI",
        )
    )

    assert scheduler is not None
    clock.now = 1.0
    scheduler.deliver_frame()
    clock.now = 2.0
    scheduler.deliver_frame()
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


def test_output_detail_keeps_operation_age_and_wait_levels() -> None:
    """Retain shared timing when logs refine the operation shown to the user."""
    clock = _Clock()
    stream = TerminalOutputStream(max_lines=20)
    presenter = SplashActivityPresenter(stream=stream, clock=clock)
    frames: list[str] = []
    presenter.textChanged.connect(frames.append)
    try:
        presenter.start(SplashActivity("Waiting", "Long wait", "Extended wait"))
        clock.now = 119
        presenter.set_detail("Loading custom node: SugarCubes.")
        assert frames[-1].startswith("Loading custom node: SugarCubes...")
        clock.now = 120
        presenter.refresh()
        assert "taking longer than usual" in frames[-1]
        assert "SugarCubes" in frames[-1]
        assert "\nThis is taking" in frames[-1]
        assert stream.snapshot()[-1] == "Long wait."
        clock.now = 121
        presenter.set_detail("Loading custom node: AnotherNode.")
        assert "taking longer than usual" in frames[-1]
        assert "AnotherNode" in frames[-1]
        clock.now = 300
        presenter.refresh()
        assert "taking much longer than expected" in frames[-1]
        presenter.clear_detail()
        assert frames[-1].startswith("Extended wait")
        presenter.clear()
        assert frames[-1] == ""
        presenter.set_detail("Starting the ComfyUI server.")
        assert frames[-1] == "Starting the ComfyUI server."
        presenter.shutdown()
        presenter.set_detail("Should not restart")
        assert "Should not restart" not in frames[-1]
    finally:
        presenter.shutdown()


def test_output_summaries_never_replace_console_activity() -> None:
    """Keep console wait feedback independent of collapsed-only output summaries."""
    clock = _Clock()
    stream = TerminalOutputStream(max_lines=20)
    presenter = SplashActivityPresenter(stream=stream, clock=clock)
    frames: list[str] = []
    presenter.textChanged.connect(frames.append)
    try:
        presenter.set_detail("Configuring ComfyUI attention.")
        assert stream.snapshot() == ()
        presenter.start(
            SplashActivity("Waiting for ComfyUI", "Long wait", "Still waiting")
        )
        stream.append_line("Using attention backend")
        presenter.set_detail("Configuring ComfyUI attention.")
        assert frames[-1] == "Configuring ComfyUI attention."
        assert stream.snapshot() == ("Using attention backend", "Waiting for ComfyUI.")
        clock.now = 1
        presenter.refresh()
        assert stream.snapshot()[-1] == "Waiting for ComfyUI.."
        assert frames[-1] == "Configuring ComfyUI attention.."
    finally:
        presenter.shutdown()
