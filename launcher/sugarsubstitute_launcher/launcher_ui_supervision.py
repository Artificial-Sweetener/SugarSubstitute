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

"""Run launcher-owned QApplications beneath the crash supervisor."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import tempfile
from typing import Protocol

from launcher.sugarsubstitute_launcher.cli import LauncherArguments
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
    InstanceRecoveryAction,
    InstanceRecoveryRequest,
)
from launcher.sugarsubstitute_launcher.launcher_ui_process import (
    build_launcher_ui_command,
    start_crash_reporter,
)
from launcher.sugarsubstitute_launcher.runtime_paths import frozen_support_path
from sugarsubstitute_shared.windows_long_paths import subprocess_path


class LauncherUiCrashSupervisor(Protocol):
    """Describe the supervision boundary used by launcher UI child modes."""

    def supervise(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> int:
        """Run one launcher UI child until a classified terminal state."""


def supervise_launcher_window(
    *,
    layout: InstallLayout,
    arguments: LauncherArguments,
    repair: bool,
    supervisor: LauncherUiCrashSupervisor | None = None,
) -> int:
    """Run setup or repair UI as a full-lifetime supervised child."""

    child_arguments = [
        "--launcher-ui-child",
        f"--install-root={subprocess_path(layout.root)}",
    ]
    if arguments.continue_install:
        child_arguments.append("--continue-install")
    if repair:
        child_arguments.append("--repair")
    if arguments.no_update_check:
        child_arguments.append("--no-update-check")
    _append_value(child_arguments, "--handoff-geometry", arguments.handoff_geometry)
    _append_value(child_arguments, "--manifest-url", arguments.manifest_url)
    _append_value(child_arguments, "--locale", arguments.locale_override)
    return _supervise(
        layout=layout,
        child_arguments=child_arguments,
        supervisor=supervisor,
    )


def supervise_instance_recovery_window(
    *,
    layout: InstallLayout,
    locale_override: str | None,
    can_end_owner: bool,
    supervisor: LauncherUiCrashSupervisor | None = None,
) -> InstanceRecoveryAction:
    """Run the Qt recovery modal in the supervised launcher UI executable."""

    with tempfile.TemporaryDirectory(
        prefix="SugarSubstitute-instance-recovery-"
    ) as temporary_directory:
        request, request_path = InstanceRecoveryRequest.create(
            Path(temporary_directory)
        )
        request = request.with_owner_termination(can_end_owner)
        request.write(request_path)
        child_arguments = [
            "--launcher-ui-child",
            f"--install-root={subprocess_path(layout.root)}",
            f"--instance-recovery-request={subprocess_path(request_path)}",
        ]
        _append_value(child_arguments, "--locale", locale_override)
        result = _supervise(
            layout=layout,
            child_arguments=child_arguments,
            supervisor=supervisor,
        )
        if result != 0:
            return InstanceRecoveryAction.EXIT
        try:
            return request.read_response()
        except (OSError, ValueError):
            return InstanceRecoveryAction.EXIT


def _supervise(
    *,
    layout: InstallLayout,
    child_arguments: Sequence[str],
    supervisor: LauncherUiCrashSupervisor | None,
) -> int:
    """Run one current-launcher child through the shared crash protocol."""

    crash_owner = supervisor or ApplicationCrashSupervisor(
        reporter_starter=start_crash_reporter,
        native_runtime_resolver=_current_native_runtime,
    )
    return crash_owner.supervise(
        layout=layout,
        command=build_launcher_ui_command(layout, child_arguments),
        environment=os.environ,
    )


def _current_native_runtime(layout: InstallLayout) -> tuple[Path, Path]:
    """Return Crashpad assets from the current bundle or source checkout."""

    support_path = frozen_support_path()
    if support_path is not None:
        runtime = support_path / "crashpad"
    else:
        repository_root = Path(__file__).resolve().parents[2]
        target_directory = layout.target.key.replace("_", "-")
        runtime = (
            repository_root / "third_party" / "bin" / "crashpad" / target_directory
        )
    return (
        runtime / layout.crashpad_handler_path.name,
        runtime / layout.crashpad_client_library_path.name,
    )


def _append_value(arguments: list[str], option: str, value: str | None) -> None:
    """Append one optional internal child argument without shell parsing."""

    if value is not None:
        arguments.append(f"{option}={value}")


__all__ = [
    "LauncherUiCrashSupervisor",
    "supervise_instance_recovery_window",
    "supervise_launcher_window",
]
