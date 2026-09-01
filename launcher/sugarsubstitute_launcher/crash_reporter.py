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
import subprocess
import sys

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
    restart: Callable[[], None] | None = None,
    presenter: CrashReportPresenter | None = None,
) -> int:
    """Show one pending crash report and acknowledge it only after dismissal."""

    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    incident = next(
        (item for item in store.pending() if item.incident_id == incident_id),
        None,
    )
    if incident is None:
        return 1

    restart_action = restart or (lambda: _restart_application(layout))
    (presenter or _present_crash_incident)(
        layout,
        incident,
        locale_override,
        restart_action,
    )
    store.acknowledge(incident_id)
    return 0


def show_pending_crash_reports(
    *,
    layout: InstallLayout,
    locale_override: str | None,
    restart: Callable[[], None],
    presenter: CrashReportPresenter | None = None,
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


def _present_crash_incident(
    layout: InstallLayout,
    incident: CrashIncident,
    locale_override: str | None,
    restart: Callable[[], None],
) -> None:
    """Render one incident through the shared localized QFluent report surface."""

    from PySide6.QtWidgets import QApplication
    from launcher.sugarsubstitute_launcher.localization import (
        build_launcher_localization_runtime,
    )
    from sugarsubstitute_shared.crash_reporting.presentation import (
        build_crash_report_presentation,
    )
    from sugarsubstitute_shared.presentation.error_report_dialog import (
        SharedErrorReportDialog,
    )
    from launcher.sugarsubstitute_launcher.ui.launcher_theme import (
        configure_launcher_theme,
    )

    application = QApplication.instance()
    if not isinstance(application, QApplication):
        application = QApplication(sys.argv[:1])
    configure_launcher_theme()
    localization_runtime = build_launcher_localization_runtime(
        application,
        layout=layout,
        locale_override=locale_override,
    )
    SharedErrorReportDialog(
        presentation=build_crash_report_presentation(incident),
        restart=restart,
    ).exec()
    del localization_runtime


def _restart_application(layout: InstallLayout) -> None:
    """Start the stable launcher so the replacement receives fresh supervision."""

    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = subprocess.CREATE_NO_WINDOW
    subprocess.Popen(  # noqa: S603
        [str(layout.executable_path), f"--install-root={layout.root}"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
        startupinfo=startupinfo,
        shell=False,
    )


__all__ = ["show_crash_report", "show_pending_crash_reports"]
