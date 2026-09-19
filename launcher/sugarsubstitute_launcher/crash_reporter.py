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

"""Present durable crash incidents through SugarSubstitute's QFluent error UI."""

from __future__ import annotations

from collections.abc import Callable

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.crash_reporting import CrashIncident, CrashIncidentStore


CrashReportPresenter = Callable[
    [InstallLayout, CrashIncident, str | None, Callable[[], None]],
    None,
]


def show_crash_report(
    *,
    layout: InstallLayout,
    incident_id: str,
    locale_override: str | None,
    restart: Callable[[], None],
    presenter: CrashReportPresenter,
) -> int:
    """Show one pending crash report and acknowledge it only after dismissal."""

    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    incident = next(
        (item for item in store.pending() if item.incident_id == incident_id),
        None,
    )
    if incident is None:
        return 1

    restart_action = restart
    restart_requested = False

    def request_restart() -> None:
        """Defer replacement until the dismissed incident has been acknowledged."""

        nonlocal restart_requested
        restart_requested = True

    presenter(
        layout,
        incident,
        locale_override,
        request_restart,
    )
    store.acknowledge(incident_id)
    if restart_requested:
        restart_action()
    return 0


def show_pending_crash_reports(
    *,
    layout: InstallLayout,
    locale_override: str | None,
    restart: Callable[[], None],
    presenter: CrashReportPresenter,
) -> int:
    """Recover every durable incident before a requested normal app launch."""

    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    pending = sorted(store.pending(), key=lambda incident: incident.occurred_at_utc)
    presented = 0
    for incident in pending:
        if (
            show_crash_report(
                layout=layout,
                incident_id=incident.incident_id,
                locale_override=locale_override,
                restart=restart,
                presenter=presenter,
            )
            == 0
        ):
            presented += 1
    return presented


__all__ = ["show_crash_report", "show_pending_crash_reports"]
