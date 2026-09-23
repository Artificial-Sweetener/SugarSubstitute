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

"""Parse internal launcher command-line flags."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from sugarsubstitute_shared.application_launch_context import ApplicationLaunchIntent


class LauncherArgumentError(ValueError):
    """Reject an inspected invocation without printing or exiting the launcher."""


class _InspectionArgumentParser(argparse.ArgumentParser):
    """Apply the launcher's grammar to another process without CLI side effects."""

    def error(self, message: str) -> NoReturn:
        """Return invalid process arguments to the inspection boundary as data."""
        raise LauncherArgumentError(message)


@dataclass(frozen=True, slots=True)
class LauncherArguments:
    """Capture parsed launcher command-line behavior switches."""

    continue_install: bool
    headless_install: bool
    verify_release_connectivity: bool
    repair: bool
    no_update_check: bool
    install_root: Path | None
    handoff_geometry: str | None
    manifest_url: str | None
    locale_override: str | None
    crash_report_incident_id: str | None
    crash_report_continues_launch: bool
    launcher_ui_child: bool
    instance_recovery_request: Path | None
    launch_intent: ApplicationLaunchIntent


def parse_launcher_args(
    argv: Sequence[str], *, report_errors: bool = True
) -> LauncherArguments:
    """Parse the shared launcher grammar for CLI execution or quiet inspection."""

    parser_type = (
        argparse.ArgumentParser if report_errors else _InspectionArgumentParser
    )
    parser = parser_type(add_help=report_errors)
    execution_mode = parser.add_mutually_exclusive_group()
    execution_mode.add_argument("--continue-install", action="store_true")
    execution_mode.add_argument("--headless-install", action="store_true")
    execution_mode.add_argument("--verify-release-connectivity", action="store_true")
    execution_mode.add_argument("--show-crash-report", type=str, default=None)
    parser.add_argument(
        "--crash-report-continues-launch", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--launcher-ui-child",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--instance-recovery-request",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--no-update-check", action="store_true")
    parser.add_argument("--install-root", type=Path, default=None)
    parser.add_argument("--handoff-geometry", type=str, default=None)
    parser.add_argument("--manifest-url", type=str, default=None)
    parser.add_argument("--locale", type=str, default=None)
    parser.add_argument(
        "--launch-intent",
        choices=tuple(intent.value for intent in ApplicationLaunchIntent),
        default=ApplicationLaunchIntent.NORMAL.value,
        help=argparse.SUPPRESS,
    )
    namespace = parser.parse_args(argv)
    if namespace.headless_install and namespace.install_root is None:
        parser.error("--headless-install requires --install-root")
    if namespace.show_crash_report and namespace.install_root is None:
        parser.error("--show-crash-report requires --install-root")
    if namespace.crash_report_continues_launch and (
        not namespace.show_crash_report or not namespace.launcher_ui_child
    ):
        parser.error(
            "--crash-report-continues-launch requires --show-crash-report and "
            "--launcher-ui-child"
        )
    if namespace.instance_recovery_request is not None and (
        not namespace.launcher_ui_child or namespace.install_root is None
    ):
        parser.error(
            "--instance-recovery-request requires --launcher-ui-child and "
            "--install-root"
        )
    return LauncherArguments(
        continue_install=namespace.continue_install,
        headless_install=namespace.headless_install,
        verify_release_connectivity=namespace.verify_release_connectivity,
        repair=namespace.repair,
        no_update_check=namespace.no_update_check,
        install_root=namespace.install_root,
        handoff_geometry=namespace.handoff_geometry,
        manifest_url=namespace.manifest_url,
        locale_override=namespace.locale,
        crash_report_incident_id=namespace.show_crash_report,
        crash_report_continues_launch=namespace.crash_report_continues_launch,
        launcher_ui_child=namespace.launcher_ui_child,
        instance_recovery_request=namespace.instance_recovery_request,
        launch_intent=ApplicationLaunchIntent(namespace.launch_intent),
    )
