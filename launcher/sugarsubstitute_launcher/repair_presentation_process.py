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

"""Keep repair presentation and crash dependencies outside replacement roots."""

from __future__ import annotations

from launcher.sugarsubstitute_launcher.process_execution import ChildProcess

from collections.abc import Mapping, Sequence
from functools import partial
from pathlib import Path

from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
    PreparedRepairRequestError,
)
from launcher.sugarsubstitute_launcher.application_lifecycle_supervisor import (
    ApplicationLifecycleSupervisor,
)
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.launcher_ui_process import (
    build_launcher_ui_command,
    present_crash_report,
)
from launcher.sugarsubstitute_launcher.platforms import launcher_target_for_key
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared.application_readiness import ApplicationReadinessSurface
from sugarsubstitute_shared.windows_long_paths import subprocess_path


class IndependentRepairPresentation:
    """Supervise the repair UI using its prepared, independently retained bundle."""

    def run(
        self, request: PreparedRepairRequest, environment: Mapping[str, str]
    ) -> int:
        """Require a painted repair surface and preserve crash reporting during mutation."""
        if request.helper_bundle_dir is None:
            raise PreparedRepairRequestError(
                "Repair presentation requires an independent launcher bundle."
            )
        target = launcher_target_for_key(request.target_key)
        installation = InstallLayout.from_root(request.install_root, target=target)
        bundle = InstallLayout.from_root(request.helper_bundle_dir, target=target)
        command = build_launcher_ui_command(
            bundle,
            (f"--repair-ui-request={subprocess_path(request.request_path)}",),
        )
        crash = ApplicationCrashSupervisor(
            reporter_starter=partial(present_crash_report, bundle_layout=bundle),
            native_runtime_resolver=lambda _installation: (
                bundle.crashpad_handler_path,
                bundle.crashpad_client_library_path,
            ),
        )

        def start_child(
            arguments: Sequence[str], child_environment: Mapping[str, str]
        ) -> tuple[ChildProcess, Path]:
            """Keep the open child log outside every replacement and quarantine root."""
            return spawn_supervised_process(
                arguments,
                environment=child_environment,
                startup_log_path=installation.root
                / ".repair"
                / "diagnostics"
                / "repair-child.log",
            )

        lifecycle = ApplicationLifecycleSupervisor(
            accepted_surfaces=(ApplicationReadinessSurface.LAUNCHER_WINDOW,),
            crash_supervisor=crash,
            process_starter=start_child,
        )
        return lifecycle.supervise(
            layout=installation,
            command=command,
            environment=environment,
        )
