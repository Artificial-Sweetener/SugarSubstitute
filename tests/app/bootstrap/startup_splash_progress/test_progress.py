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

"""Verify startup queue boundaries reach completion and activity surfaces."""

from __future__ import annotations

from substitute.app.bootstrap.gui_startup_queue import GuiStartupProgress
from substitute.app.bootstrap.startup_splash_progress import StartupSplashProgress
from sugarsubstitute_shared.launch_splash.progress import SplashProgress


class _Splash:
    """Record queue projection without importing a Qt surface."""

    def __init__(self) -> None:
        """Initialize progress and observed-work records."""

        self.progress: list[SplashProgress] = []
        self.activity_calls = 0

    def set_progress(self, progress: SplashProgress, *, status: str) -> None:
        """Record one projected startup boundary."""

        assert status == "Preparing the application interface."
        self.progress.append(progress)

    def record_activity(self) -> None:
        """Record one producer-confirmed startup work event."""

        self.activity_calls += 1

    def close(self) -> None:
        """Satisfy the startup splash lifecycle contract."""


def test_queue_boundaries_pulse_and_reserve_ready_surface_completion() -> None:
    """Relay every real task boundary while retaining the final paint unit."""

    splash = _Splash()
    projection = StartupSplashProgress(lambda: splash)

    projection.queue_progress(GuiStartupProgress("build_shell", 2, 4, False))
    projection.queue_progress(GuiStartupProgress("build_shell", 3, 6, True))

    assert splash.activity_calls == 2
    assert splash.progress == [SplashProgress(2, 5), SplashProgress(3, 7)]
