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

from launcher.sugarsubstitute_launcher.cli import LauncherArguments
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


def route_explicit_crash_operation(args: LauncherArguments) -> int | None:
    """Run one explicit crash reporter or supervised restart invocation."""

    if args.crash_report_incident_id is not None:
        if args.install_root is None:
            raise ValueError("Crash reporting requires an explicit install root.")
        from launcher.sugarsubstitute_launcher.crash_reporter import (
            show_crash_report,
        )

        return show_crash_report(
            layout=InstallLayout.from_root(args.install_root),
            incident_id=args.crash_report_incident_id,
            locale_override=args.locale_override,
        )
    if not args.restart_application:
        return None
    if args.install_root is None:
        raise ValueError("Application restart requires an explicit install root.")
    from launcher.sugarsubstitute_launcher.restart_supervision import (
        supervise_restarted_application,
    )

    return supervise_restarted_application(
        layout=InstallLayout.from_root(args.install_root)
    )


def recover_pending_crash_reports(
    *,
    layout: InstallLayout,
    locale_override: str | None,
) -> int:
    """Present durable missed reports before continuing a requested launch."""

    from launcher.sugarsubstitute_launcher.crash_reporter import (
        show_pending_crash_reports,
    )

    return show_pending_crash_reports(
        layout=layout,
        locale_override=locale_override,
        restart=lambda: None,
    )


__all__ = ["recover_pending_crash_reports", "route_explicit_crash_operation"]
