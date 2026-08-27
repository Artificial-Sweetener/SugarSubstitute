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

"""Complete update and app-process handoff after splash visibility."""

from __future__ import annotations

import os
from pathlib import Path

from launcher.sugarsubstitute_launcher.application_launch import (
    installed_application_environment,
)
from launcher.sugarsubstitute_launcher.candidate_update_launch import (
    launch_prepared_update,
)
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process import (
    build_app_launch_command,
    start_detached,
)
from launcher.sugarsubstitute_launcher.release_sources import (
    ReleaseSource,
    release_source_from_config,
)
from launcher.sugarsubstitute_launcher.splash_session import (
    LauncherSplashSession,
    append_splash_session_args,
)
from launcher.sugarsubstitute_launcher.update_orchestrator import (
    LauncherUpdateOrchestrator,
)
from sugarsubstitute_shared.application_launch_guard import ApplicationLaunchGuard
from sugarsubstitute_shared.launcher_update.process import schedule_launcher_update


_PRE_LAUNCH_MANIFEST_TIMEOUT_SECONDS = 3.0


def complete_installed_app_handoff(
    *,
    layout: InstallLayout,
    launch_guard: ApplicationLaunchGuard,
    locale_argument: str,
    no_update_check: bool,
    splash_session: LauncherSplashSession | None,
) -> None:
    """Run update policy and start the installed app behind its visible splash."""

    config = LauncherConfig.load(layout.config_path)
    update_result = LauncherUpdateOrchestrator().run(
        layout=layout,
        config=config,
        release_source=_normal_launch_release_source(config),
        no_update_check=no_update_check,
        progress=splash_session.client if splash_session is not None else None,
    )
    if update_result.launcher_update_request_path is not None:
        if splash_session is not None:
            splash_session.client.close()
        schedule_launcher_update(
            request_path=Path(update_result.launcher_update_request_path),
            runtime_python=layout.runtime_python,
            app_dir=layout.app_dir,
            relaunch=True,
            wait_pid=os.getpid(),
        )
        return

    app_command = append_splash_session_args(
        build_app_launch_command(
            layout=layout,
            extra_args=(locale_argument,),
        ),
        splash_session,
    )
    if update_result.pending_activation is not None:
        launch_prepared_update(
            layout=layout,
            command=app_command,
            initial_guard=launch_guard,
            activation=update_result.pending_activation,
        )
        return
    start_detached(
        app_command,
        environment=installed_application_environment(
            launch_guard,
            remote_failure_reason=update_result.failure_reason,
        ),
    )


def _normal_launch_release_source(config: LauncherConfig) -> ReleaseSource | None:
    """Return the bounded release source used by post-splash update checks."""

    return release_source_from_config(
        config.release_source,
        timeout_seconds=_PRE_LAUNCH_MANIFEST_TIMEOUT_SECONDS,
    )


__all__ = ["complete_installed_app_handoff"]
