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

"""Prove the old shell remains recoverable behind nodepack recovery splash."""

from __future__ import annotations

from collections.abc import Callable

from sugarsubstitute_shared.launch_splash.activity import (
    SplashActivity,
    render_splash_activity,
)
from substitute.app.bootstrap.nodepack_recovery_handoff import (
    NodepackRecoveryHandoff,
)
from sugarsubstitute_shared.presentation.localization import app_text


class _Shell:
    """Record the shell's externally visible state."""

    def __init__(self, events: list[str]) -> None:
        """Start with a visible shell."""

        self.events = events
        self.visible = True

    def hide(self) -> None:
        """Record a handoff hiding the old shell."""

        self.visible = False
        self.events.append("shell:hidden")

    def show(self) -> None:
        """Record recovery restoring the old shell."""

        self.visible = True
        self.events.append("shell:visible")


class _Splash:
    """Record one recovery splash without a native Qt dependency."""

    def __init__(self, events: list[str]) -> None:
        """Initialize a hidden, cancellable splash."""

        self.events = events
        self.visible = False
        self.cancellation_enabled = True
        self.lines: list[str] = []
        self.activities: list[SplashActivity] = []

    def set_cancellation_enabled(self, enabled: bool) -> None:
        """Record the install's non-cancellable interval."""

        self.cancellation_enabled = enabled

    def center_on_screen(self) -> None:
        """Record splash positioning before visibility."""

        self.events.append("splash:centered")

    def append_log(self, line: str) -> None:
        """Retain localized status copy."""

        self.lines.append(line)

    def start_activity(self, activity: SplashActivity) -> None:
        """Record each animated stage independently of the durable console."""

        self.activities.append(activity)

    def show(self) -> None:
        """Record splash visibility."""

        self.visible = True
        self.events.append("splash:visible")

    def dismiss(self) -> None:
        """Record splash dismissal."""

        self.visible = False
        self.events.append("splash:hidden")

    def deleteLater(self) -> None:
        """Record retirement of the Qt-owned surface."""

        self.events.append("splash:retired")


def _handoff(
    *,
    shell: _Shell,
    splash: _Splash,
    jobs_active: bool = False,
    reload_gui: Callable[[], bool] = lambda: True,
) -> NodepackRecoveryHandoff:
    """Compose the real handoff policy against observable boundary fakes."""

    return NodepackRecoveryHandoff(
        current_shell=lambda: shell,
        has_cancellable_jobs=lambda: jobs_active,
        create_splash=lambda: splash,
        reload_gui=reload_gui,
    )


def test_approved_recovery_hides_shell_until_fresh_gui_can_show() -> None:
    """The splash owns the visible interval from install through GUI reload."""

    events: list[str] = []
    shell = _Shell(events)
    splash = _Splash(events)
    handoff = _handoff(shell=shell, splash=splash)

    assert handoff.begin()
    assert not shell.visible
    assert splash.visible
    assert not splash.cancellation_enabled
    assert splash.lines == []
    assert render_splash_activity(splash.activities[0], 0) == (
        "Installing required custom nodes."
    )
    assert render_splash_activity(splash.activities[0], 1) == (
        "Installing required custom nodes.."
    )

    handoff.report(app_text("Restarting ComfyUI to apply updated dependencies."))
    assert splash.lines == ["Installing required custom nodes"]
    assert splash.activities[-1].initial_text == (
        "Restarting ComfyUI to apply updated dependencies."
    )
    assert handoff.reload()
    assert splash.lines[-1] == "Restarting ComfyUI to apply updated dependencies."
    assert splash.activities[-1].initial_text == "Preparing your saved workspace."
    handoff.finish()

    assert not splash.visible
    assert not shell.visible
    assert events.index("splash:hidden") > events.index("shell:hidden")


def test_failed_recovery_restores_old_shell_and_releases_splash() -> None:
    """An install failure must never strand the user behind a hidden shell."""

    events: list[str] = []
    shell = _Shell(events)
    splash = _Splash(events)
    handoff = _handoff(shell=shell, splash=splash)

    assert handoff.begin()
    handoff.cancel()

    assert shell.visible
    assert not splash.visible
    assert events[-1] == "shell:visible"


def test_refused_gui_reload_restores_the_old_shell() -> None:
    """A failed final handoff leaves the original workflow accessible."""

    events: list[str] = []
    shell = _Shell(events)
    splash = _Splash(events)
    handoff = _handoff(shell=shell, splash=splash, reload_gui=lambda: False)

    assert handoff.begin()
    assert not handoff.reload()
    assert shell.visible
    assert not splash.visible


def test_active_generation_prevents_recovery_handoff() -> None:
    """Installing nodes must not hide a shell with cancellable generation work."""

    events: list[str] = []
    shell = _Shell(events)
    splash = _Splash(events)
    handoff = _handoff(shell=shell, splash=splash, jobs_active=True)

    assert not handoff.begin()
    assert shell.visible
    assert not splash.visible
    assert events == []
