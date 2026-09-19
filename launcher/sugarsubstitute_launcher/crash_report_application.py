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

"""Own the standalone crash-report application's Qt and supervisor lifetime."""

from __future__ import annotations

from launcher.sugarsubstitute_launcher.process_execution import start_detached_handoff

from collections.abc import Callable
from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

from launcher.sugarsubstitute_launcher.crash_reporter import show_crash_report
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.resources import launcher_icon
from launcher.sugarsubstitute_launcher.localization import (
    build_launcher_localization_runtime,
)
from launcher.sugarsubstitute_launcher.ui.launcher_theme import configure_launcher_theme
from sugarsubstitute_shared.crash_reporting import (
    CrashIncident,
    CrashIncidentStore,
)
from sugarsubstitute_shared.crash_reporting.redaction import CrashReportRedactor
from sugarsubstitute_shared.crash_reporting.presentation import (
    build_crash_report_presentation,
)
from sugarsubstitute_shared.qt_application_instance_control import (
    request_supervised_application_restart,
    start_application_instance_control,
    stop_application_instance_control,
)
from sugarsubstitute_shared.presentation.error_report_presentation import (
    ErrorReportPresentation,
)


def run_crash_report_application(
    *,
    layout: InstallLayout,
    incident_id: str,
    locale_override: str | None,
    continue_launch: bool,
) -> int:
    """Keep report controls alive until acknowledgement and restart are complete."""

    application = QApplication.instance()
    if not isinstance(application, QApplication):
        application = QApplication(sys.argv[:1])
    control = start_application_instance_control()
    try:
        configure_launcher_theme()
        application.setWindowIcon(launcher_icon())
        localization = build_launcher_localization_runtime(
            application, layout=layout, locale_override=locale_override
        )
        try:
            return show_crash_report(
                layout=layout,
                incident_id=incident_id,
                locale_override=locale_override,
                restart=(lambda: None)
                if continue_launch
                else lambda: _restart_application(layout),
                presenter=_present_crash_incident,
            )
        finally:
            localization.manager.close()
    finally:
        if control is not None:
            stop_application_instance_control()


def _present_crash_incident(
    layout: InstallLayout,
    incident: CrashIncident,
    _locale_override: str | None,
    restart: Callable[[], None],
) -> None:
    """Present a report in its own window after application locale composition."""

    from sugarsubstitute_shared.presentation.error_report_window import (
        SharedErrorReportWindow,
    )

    window = SharedErrorReportWindow(
        presentation=_build_complete_crash_report(layout, incident), restart=restart
    )
    try:
        window.exec()
    finally:
        window.deleteLater()


def _build_complete_crash_report(
    layout: InstallLayout,
    incident: CrashIncident,
) -> ErrorReportPresentation:
    """Build one copyable report containing every readable attached crash log."""

    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    redactor = CrashReportRedactor(home=Path.home(), install_root=layout.root)
    text_attachments = tuple(
        (filename, redactor.complete_text(content))
        for filename, content in store.read_text_attachments(incident)
    )
    return build_crash_report_presentation(
        incident,
        text_attachments=text_attachments,
    )


def _restart_application(layout: InstallLayout) -> None:
    """Route restart through the retained supervisor or elect a new standalone owner."""

    if request_supervised_application_restart():
        return
    start_detached_handoff(
        [str(layout.executable_path), f"--install-root={layout.root}"]
    )
