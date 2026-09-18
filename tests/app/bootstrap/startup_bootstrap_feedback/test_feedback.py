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

"""Verify pre-shell feedback without initializing the main application."""

from substitute.app.bootstrap.launch_splash_client import NullLaunchSplashClient
from substitute.app.bootstrap.startup_bootstrap_feedback import (
    BootstrapStage,
    StartupBootstrapFeedback,
)
from sugarsubstitute_shared.launch_splash.activity import SplashActivity


class RecordingSplash(NullLaunchSplashClient):
    """Capture the early transport boundary without creating windows."""

    def __init__(self) -> None:
        """Keep emitted console and caption events in delivery order."""
        self.events: list[str] = []

    def clear_activity(self) -> None:
        """Record removal of the preceding transient caption."""
        self.events.append("clear")

    def append_log(self, line: str) -> None:
        """Record a durable console milestone."""
        self.events.append(line)

    def start_activity(self, activity: SplashActivity) -> None:
        """Record the independently animated caption source."""
        self.events.append(activity.initial_text)


def test_bootstrap_feedback_localizes_console_and_caption_together() -> None:
    """Announce each actual stage and replace the previous activity first."""
    splash = RecordingSplash()
    feedback = StartupBootstrapFeedback(
        splash, translate=lambda text: "localized:" + text
    )
    feedback.report(BootstrapStage.INSTALLATION)
    feedback.report(BootstrapStage.WORKSPACE)
    assert splash.events == [
        "clear",
        "localized:Checking the installation.",
        "localized:Checking the installation.",
        "clear",
        "localized:Preparing your saved workspace.",
        "localized:Preparing your saved workspace.",
    ]


def test_bootstrap_feedback_without_splash_does_not_translate() -> None:
    """Leave headless startup independent of display and translation resources."""
    translations: list[str] = []

    def translate(text: str) -> str:
        """Record translation requests without requiring a catalog."""
        translations.append(text)
        return text

    feedback = StartupBootstrapFeedback(translate=translate)
    for stage in BootstrapStage:
        feedback.report(stage)
    assert translations == []
