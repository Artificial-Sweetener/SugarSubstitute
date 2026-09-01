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

"""Qualify the launcher's independent shared crash-report presentation."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QAbstractButton, QApplication
from shiboken6 import delete

from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashBoundary,
    CrashIncident,
    CrashKind,
)
from sugarsubstitute_shared.crash_reporting import presentation as crash_presentation
from sugarsubstitute_shared.issue_tracker import SUGARSUBSTITUTE_ISSUES_URL
from sugarsubstitute_shared.presentation.error_report_dialog import (
    SharedErrorReportDialog,
)
from tests.support.qt.lifecycle import ensure_qt_application


pytestmark = pytest.mark.usefixtures("qt_clipboard_owner")


def test_launcher_crash_surface_copies_opens_github_and_restarts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The launcher-owned report must expose the complete shared recovery surface."""

    application = ensure_qt_application()
    opened_urls: list[str] = []
    restart_calls: list[None] = []

    class DesktopServices:
        """Capture the trusted URL requested by the production action."""

        @staticmethod
        def openUrl(url: QUrl) -> bool:
            """Record one URL and report successful shell handoff."""

            opened_urls.append(url.toString())
            return True

    monkeypatch.setattr(crash_presentation, "QDesktopServices", DesktopServices)
    incident = CrashIncident(
        incident_id="launcher-presentation-incident",
        run_id="launcher-presentation-run",
        occurred_at_utc="2026-08-31T12:00:00+00:00",
        kind=CrashKind.PYTHON_UNHANDLED,
        boundary=CrashBoundary.PROCESS_MAIN,
        attribution=CrashAttribution.CONFIRMED,
        summary="Qualified launcher crash",
        process_id=42,
        exception_type="RuntimeError",
        traceback=("Traceback line", "RuntimeError: qualified"),
        application_version="0.22.0",
        platform="Windows",
        python_version="3.12",
    )
    report = crash_presentation.build_crash_report_presentation(incident)
    dialog = SharedErrorReportDialog(
        presentation=report,
        restart=lambda: restart_calls.append(None),
    )

    try:
        assert dialog._report_issue_button is not None
        assert dialog._restart_button is not None
        footer_actions = [
            widget.text()
            for index in range(dialog.buttonLayout.count())
            if (widget := dialog.buttonLayout.itemAt(index).widget()) is not None
            and isinstance(widget, QAbstractButton)
        ]
        assert footer_actions == [
            "Copy report",
            "Report issue",
            "Close",
            "Restart SugarSubstitute",
        ]
        assert "launcher-presentation-incident" in report.report_text
        assert "RuntimeError: qualified" in report.report_text
        assert SUGARSUBSTITUTE_ISSUES_URL in report.report_text

        dialog._toggle_details()
        dialog._copy_button.click()
        dialog._report_issue_button.click()
        dialog._restart_button.click()

        assert dialog._details_button.text() == "Hide report"
        assert QApplication.clipboard().text() == report.report_text
        assert opened_urls == [SUGARSUBSTITUTE_ISSUES_URL]
        assert restart_calls == [None]
    finally:
        dialog.close()
        delete(dialog)
        application.processEvents()
