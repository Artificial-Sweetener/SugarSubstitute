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

"""Adopt an application-authorized restart under full crash supervision."""

from __future__ import annotations

import os

from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process import build_app_launch_command
from sugarsubstitute_shared.application_launch_guard import (
    clear_inherited_application_launch_token,
    inherited_application_launch_token,
)
from sugarsubstitute_shared.application_runtime_mode import (
    packaged_application_environment,
)


def supervise_restarted_application(*, layout: InstallLayout) -> int:
    """Run the authorized replacement app beneath a fresh crash contract."""

    restart_environment = dict(os.environ)
    if inherited_application_launch_token(restart_environment) is None:
        raise RuntimeError("Application restart supervision requires a handoff token.")
    clear_inherited_application_launch_token()
    return ApplicationCrashSupervisor().supervise(
        layout=layout,
        command=build_app_launch_command(layout=layout),
        environment=packaged_application_environment(restart_environment),
    )


__all__ = ["supervise_restarted_application"]
