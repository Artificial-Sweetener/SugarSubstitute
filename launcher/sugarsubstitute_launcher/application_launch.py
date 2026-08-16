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

"""Own installed-application launch authority for shortcut invocations."""

from __future__ import annotations

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_launch_guard import ApplicationLaunchGuard
from sugarsubstitute_shared.startup_remote_access import StartupRemoteAccess


def enter_installed_application_launch(
    layout: InstallLayout,
) -> ApplicationLaunchGuard | None:
    """Claim one shortcut launch and authorize its single app child."""

    return ApplicationLaunchGuard.enter(
        layout.root,
        allow_initial_handoff=True,
    )


def installed_application_environment(
    launch_guard: ApplicationLaunchGuard,
    *,
    remote_failure_reason: str | None,
) -> dict[str, str]:
    """Build one app-child environment with the launcher's remote outcome."""

    remote_access = StartupRemoteAccess()
    if remote_failure_reason is not None:
        remote_access.degrade(reason=remote_failure_reason)
    return remote_access.child_environment(launch_guard.initial_handoff_environment())


__all__ = ["enter_installed_application_launch", "installed_application_environment"]
