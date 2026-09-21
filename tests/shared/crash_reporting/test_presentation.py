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
from sugarsubstitute_shared.crash_reporting.diagnostic_context import (
    CrashDiagnosticContext,
    DiagnosticValue,
)
from sugarsubstitute_shared.issue_tracker import SUGARSUBSTITUTE_ISSUES_URL
from sugarsubstitute_shared.presentation.error_report_window import (
    SharedErrorReportWindow,
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
    report = crash_presentation.build_crash_report_presentation(
        incident,
        text_attachments=(("python-fault.log", "Thread 0x1\nframe.py:42"),),
    )
    dialog = SharedErrorReportWindow(
        presentation=report,
        restart=lambda: restart_calls.append(None),
    )

    try:
        assert dialog.content._report_issue_button is not None
        assert dialog.content._restart_button is not None
        footer_actions = [
            widget.text()
            for index in range(dialog.content._footer_layout.count())
            if (item := dialog.content._footer_layout.itemAt(index)) is not None
            and (widget := item.widget()) is not None
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
        assert "Diagnostic logs" in report.report_text
        assert "[python-fault.log]\nThread 0x1\nframe.py:42" in report.report_text
        assert SUGARSUBSTITUTE_ISSUES_URL in report.report_text

        dialog.content._toggle_details()
        dialog.content._copy_button.click()
        dialog.content._report_issue_button.click()
        dialog.content._restart_button.click()

        assert dialog.content._details_button.text() == "Hide report"
        assert QApplication.clipboard().text() == report.report_text
        assert opened_urls == [SUGARSUBSTITUTE_ISSUES_URL]
        assert restart_calls == [None]
    finally:
        dialog.close()
        delete(dialog)
        application.processEvents()


def test_unclean_report_omits_empty_evidence_and_exposes_lifecycle_state() -> None:
    """A sparse abnormal exit must remain truthful rather than display fake sections."""

    incident = CrashIncident(
        incident_id="unclean-report",
        run_id="unclean-run",
        occurred_at_utc="2026-09-20T20:00:00+00:00",
        kind=CrashKind.ABNORMAL_EXIT,
        boundary=CrashBoundary.SUPERVISOR,
        attribution=CrashAttribution.UNCLEAN_TERMINATION,
        summary="The process exited without a clean receipt.",
        process_id=42,
        exit_code=1,
        application_version="0.23.5",
        platform="Windows-11",
        python_version="3.12",
        launch_arguments=("main.py",),
        metadata={
            "termination_reason": "unknown",
            "exit_intent_state": "missing",
            "exit_receipt_state": "missing",
            "python_fault_log": "empty_or_missing",
            "startup_output": "empty_or_missing",
        },
        diagnostic_context=_diagnostic_context(),
    )

    report = crash_presentation.build_crash_report_presentation(
        incident,
        text_attachments=(("python-fault.log", "\r\n"),),
    ).report_text

    assert "Kind: abnormal_exit" in report
    assert "termination_reason: unknown" in report
    assert "exit_intent_state: missing" in report
    assert "exit_receipt_state: missing" in report
    assert "SugarSubstitute payload version: 0.24.1" in report
    assert "Supervising launcher version: 0.24.1" in report
    assert "ComfyUI version: 0.28.0" in report
    assert "Operating system: Windows 11 build 26100" in report
    assert "Physical memory: 64.0 GiB" in report
    assert "GPU: NVIDIA GeForce RTX 5090" in report
    assert "Traceback\n---------" not in report
    assert "Diagnostic logs\n---------------" not in report
    assert report.rstrip().endswith("Launch arguments: main.py")


def test_startup_failure_is_not_presented_as_an_application_crash() -> None:
    """A launcher-confirmed readiness failure must keep its startup identity."""

    incident = CrashIncident(
        incident_id="startup-report",
        run_id="startup-run",
        occurred_at_utc="2026-09-20T20:00:00+00:00",
        kind=CrashKind.STARTUP,
        boundary=CrashBoundary.SUPERVISOR,
        attribution=CrashAttribution.CONFIRMED,
        summary="The launcher stopped a candidate after readiness failed.",
        process_id=42,
        exit_code=1,
        metadata={"termination_reason": "readiness_failure"},
    )

    presentation = crash_presentation.build_crash_report_presentation(incident)

    assert str(presentation.title) == "SugarSubstitute could not finish starting"
    assert "Kind: startup" in presentation.report_text
    assert "Operation: application_startup" in presentation.report_text
    assert "SugarSubstitute crashed" not in presentation.report_text


def test_readiness_timeout_names_supervisor_termination_and_deadline() -> None:
    """A launcher timeout must not masquerade as an internal application crash."""

    incident = CrashIncident(
        incident_id="readiness-timeout",
        run_id="readiness-timeout-run",
        occurred_at_utc="2026-09-21T20:00:00+00:00",
        kind=CrashKind.STARTUP_READINESS_TIMEOUT,
        boundary=CrashBoundary.SUPERVISOR,
        attribution=CrashAttribution.CONFIRMED,
        summary="The launcher terminated the application after readiness timed out.",
        process_id=42,
        exit_code=1,
        metadata={
            "termination_reason": "readiness_failure",
            "readiness_timeout_seconds": "3600.0",
            "readiness_failure_kind": "timeout",
            "readiness_termination_action": "terminated",
        },
    )

    report = crash_presentation.build_crash_report_presentation(incident).report_text

    assert "Kind: startup_readiness_timeout" in report
    assert "Operation: application_startup" in report
    assert "readiness_timeout_seconds: 3600.0" in report
    assert "readiness_termination_action: terminated" in report
    assert "SugarSubstitute crashed" not in report


def _diagnostic_context() -> CrashDiagnosticContext:
    """Return complete deterministic report identity for presentation proof."""

    def value(content: str, source: str) -> DiagnosticValue:
        """Create one concise available test value."""

        return DiagnosticValue.available(content, source=source)

    return CrashDiagnosticContext(
        substitute_version=value("0.24.1", "application_payload"),
        substitute_release_version=value("0.24.1", "launcher_state"),
        supervising_launcher_version=value("0.24.1", "running_launcher"),
        installed_launcher_version=value("0.24.1", "launcher_installation_record"),
        comfyui_version=value("0.28.0", "comfyui_version.py"),
        comfyui_commit=value("0123456789abcdef", "comfyui_git_head"),
        operating_system=value("Windows 11 build 26100", "python_platform"),
        system_architecture=value("AMD64", "python_platform"),
        python_version=value("3.13.12", "python_runtime"),
        python_architecture=value("64-bit", "python_runtime"),
        processor=value("Intel Core i9-14900K", "python_platform"),
        logical_processor_count=value("32", "operating_system"),
        physical_memory=value("64.0 GiB", "psutil"),
        gpu=value("NVIDIA GeForce RTX 5090", "nvidia-smi"),
        readiness_schema=value("5", "running_launcher"),
    )
