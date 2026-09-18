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

"""Report pre-shell startup work through the early splash without importing UI services."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from substitute.app.bootstrap.launch_splash_client import LaunchSplashClient
from sugarsubstitute_shared.launch_splash.activity import SplashActivity
from sugarsubstitute_shared.localization import app_text


class BootstrapStage(Enum):
    """Name meaningful pre-shell work independently of its localized presentation."""

    COMPONENTS = "components"
    INSTALLATION = "installation"
    SERVICES = "services"
    WORKSPACE = "workspace"
    INTERFACE = "interface"


class StartupBootstrapFeedback:
    """Keep console milestones and animated early captions on the same stage."""

    def __init__(
        self,
        splash: LaunchSplashClient | None = None,
        *,
        translate: Callable[[str], str] = str,
    ) -> None:
        """Accept the pre-QApplication translator and the existing splash transport."""
        self._splash = splash
        self._translate = translate

    def report(self, stage: BootstrapStage) -> None:
        """Announce actual work before it begins without inventing completion percentages."""
        if self._splash is None:
            return
        messages = {
            BootstrapStage.COMPONENTS: app_text("Loading application components."),
            BootstrapStage.INSTALLATION: app_text("Checking the installation."),
            BootstrapStage.SERVICES: app_text("Preparing application services."),
            BootstrapStage.WORKSPACE: app_text("Preparing your saved workspace."),
            BootstrapStage.INTERFACE: app_text("Preparing the application interface."),
        }
        message = self._translate(messages[stage])
        self._splash.clear_activity()
        self._splash.append_log(message)
        self._splash.start_activity(SplashActivity(message, message, message))
