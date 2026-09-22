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

"""Build launcher commands and route intentional installed-supervisor handoffs."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_execution import start_detached_handoff
from sugarsubstitute_shared.application_launch_context import (
    ApplicationLaunchIntent,
    application_launch_intent_argument,
    application_launch_install_root,
)
from sugarsubstitute_shared.crash_reporting.protocol import (
    without_crash_supervision_environment,
)
from sugarsubstitute_shared.windows_long_paths import (
    subprocess_path,
)


def build_continue_install_command(
    *, layout: InstallLayout, handoff_geometry: str | None = None
) -> list[str]:
    """Build the command that resumes setup from the installed launcher."""

    command = [
        subprocess_path(layout.executable_path),
        "--continue-install",
        f"--install-root={subprocess_path(layout.root)}",
        application_launch_intent_argument(ApplicationLaunchIntent.SETUP),
    ]
    if handoff_geometry:
        command.append(f"--handoff-geometry={handoff_geometry}")
    return command


def build_app_launch_command(
    *,
    layout: InstallLayout,
    extra_args: Sequence[str] = (),
    launch_intent: ApplicationLaunchIntent = ApplicationLaunchIntent.NORMAL,
) -> list[str]:
    """Build the command that starts the source payload with managed Python."""

    return [
        subprocess_path(layout.runtime_python),
        subprocess_path(layout.app_entrypoint),
        f"--install-root={subprocess_path(layout.root)}",
        *(
            [application_launch_intent_argument(launch_intent)]
            if launch_intent is not ApplicationLaunchIntent.NORMAL
            else []
        ),
        *extra_args,
    ]


def build_installed_launcher_handoff_command(
    app_command: Sequence[str],
) -> list[str]:
    """Route a prepared app handoff back through its stable supervisor."""

    install_root = application_launch_install_root(app_command, app_root=Path.cwd())
    layout = InstallLayout.from_root(install_root)
    forwarded_arguments = [
        argument
        for argument in app_command
        if argument.startswith(("--handoff-geometry=", "--locale=", "--launch-intent="))
    ]
    return [
        subprocess_path(layout.executable_path),
        f"--install-root={subprocess_path(layout.root)}",
        *forwarded_arguments,
    ]


def start_installed_launcher_handoff(app_command: Sequence[str]) -> None:
    """Start the installed launcher that will supervise the prepared app."""

    from sugarsubstitute_shared.qt_application_instance_control import (
        active_application_supervisor_identity,
    )
    from sugarsubstitute_shared.supervisor_handoff import with_supervisor_handoff

    environment = without_crash_supervision_environment()
    supervisor_identity = active_application_supervisor_identity()
    if supervisor_identity is not None:
        environment = with_supervisor_handoff(environment, supervisor_identity)
    start_detached_handoff(
        build_installed_launcher_handoff_command(app_command),
        environment=environment,
    )
