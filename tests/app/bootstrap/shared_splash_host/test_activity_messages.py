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

"""Prove shared splash-host activity dispatch without a visible process."""

from __future__ import annotations

from typing import Any, cast

from sugarsubstitute_shared.launch_splash import SplashActivity, SplashSessionMessage

from substitute.app.bootstrap.shared_splash_host import _handle_session_message


class _Splash:
    """Record the splash calls made by authenticated host messages."""

    def __init__(self) -> None:
        """Create empty call logs."""

        self.activities: list[SplashActivity] = []
        self.lines: list[str] = []
        self.clear_calls = 0
        self.close_calls = 0

    def start_activity(self, activity: SplashActivity) -> None:
        """Record one activity start."""

        self.activities.append(activity)

    def clear_activity(self) -> None:
        """Record one activity clear."""

        self.clear_calls += 1

    def append_log(self, line: str) -> None:
        """Record one durable log line."""

        self.lines.append(line)

    def close(self) -> None:
        """Record host-requested splash closure."""

        self.close_calls += 1


class _Application:
    """Record shared host application shutdown."""

    def __init__(self) -> None:
        """Initialize shutdown tracking."""

        self.quit_calls = 0

    def quit(self) -> None:
        """Record one event-loop quit request."""

        self.quit_calls += 1


def test_shared_splash_host_dispatches_activity_across_application_handoff() -> None:
    """Keep one splash receptive to activity, logs, cleanup, and final closure."""

    activity = SplashActivity(
        initial_text="Updating SugarCubes",
        long_wait_text="Updating SugarCubes is taking longer than usual",
        extended_wait_text="Still updating SugarCubes—network may be slow",
    )
    splash = _Splash()
    application = _Application()
    messages = (
        SplashSessionMessage("activity", "token", activity=activity),
        SplashSessionMessage("log", "token", line="Downloaded package metadata."),
        SplashSessionMessage("clear_activity", "token"),
        SplashSessionMessage("close", "token"),
    )

    for message in messages:
        _handle_session_message(
            message,
            splash=splash,
            app=cast(Any, application),
        )

    assert splash.activities == [activity]
    assert splash.lines == ["Downloaded package metadata."]
    assert splash.clear_calls == 1
    assert splash.close_calls == 1
    assert application.quit_calls == 1
