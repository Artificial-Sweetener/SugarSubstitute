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

"""Route launcher crash-report, recovery, and restart operations."""

from __future__ import annotations

from collections.abc import Callable
import logging

from launcher.sugarsubstitute_launcher.cli import LauncherArguments
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.launcher_ui_process import run_crash_reporter
from sugarsubstitute_shared.crash_reporting import CrashIncidentStore


CrashReportRunner = Callable[[InstallLayout, str, str | None], int]
_LOGGER = logging.getLogger(__name__)


def route_explicit_crash_operation(
    args: LauncherArguments,
    *,
    reporter_runner: CrashReportRunner | None = None,
) -> int | None:
    """Delegate crash reporting unless this is the Qt-capable child."""

    if args.crash_report_incident_id is not None:
        if args.install_root is None:
            raise ValueError("Crash reporting requires an explicit install root.")
        layout = InstallLayout.from_root(args.install_root)
        if not args.launcher_ui_child:
            runner = reporter_runner or run_crash_reporter
            return runner(
                layout,
                args.crash_report_incident_id,
                args.locale_override,
            )
        from launcher.sugarsubstitute_launcher.crash_reporter import (
            show_crash_report,
        )

        return show_crash_report(
            layout=layout,
            incident_id=args.crash_report_incident_id,
            locale_override=args.locale_override,
        )
    return None


def recover_pending_crash_reports(
    *,
    layout: InstallLayout,
    locale_override: str | None,
    reporter_runner: CrashReportRunner | None = None,
) -> int:
    """Delegate missed reports without treating presentation as app readiness."""

    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    pending = sorted(store.pending(), key=lambda incident: incident.occurred_at_utc)
    runner = reporter_runner or run_crash_reporter
    recovered = 0
    for incident in pending:
        try:
            return_code = runner(layout, incident.incident_id, locale_override)
        except Exception:
            _LOGGER.exception(
                "Pending crash report could not be presented; continuing launch. "
                "| incident_id=%s install_root=%s",
                incident.incident_id,
                layout.root,
            )
            continue
        if return_code == 0:
            recovered += 1
        else:
            _LOGGER.warning(
                "Pending crash reporter exited unsuccessfully; continuing launch. "
                "| incident_id=%s install_root=%s return_code=%d",
                incident.incident_id,
                layout.root,
                return_code,
            )
    return recovered


__all__ = ["recover_pending_crash_reports", "route_explicit_crash_operation"]
