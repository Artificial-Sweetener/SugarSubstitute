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

"""Verify crash incidents use the existing structured error experience."""

from __future__ import annotations

from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashBoundary,
    CrashIncident,
    CrashKind,
)
from substitute.application.crash_reports import build_crash_error_report
from substitute.application.errors import render_error_report


def test_confirmed_crash_projects_every_diagnostic_into_standard_report() -> None:
    """Crash presentation should retain IDs, traceback, runtime, and issue action."""

    incident = CrashIncident(
        incident_id="incident-1",
        run_id="run-1",
        occurred_at_utc="2026-08-31T12:00:00+00:00",
        kind=CrashKind.NATIVE,
        boundary=CrashBoundary.NATIVE_HANDLER,
        attribution=CrashAttribution.CONFIRMED,
        summary="Native access violation",
        process_id=42,
        exception_type="EXCEPTION_ACCESS_VIOLATION",
        exception_message="Access violation",
        traceback=("frame one", "frame two"),
        exit_code=-1073741819,
        application_version="0.22.0",
        platform="Windows-11",
        python_version="3.12",
        attachments=("minidump.dmp",),
    )

    report = build_crash_error_report(incident)
    rendered = render_error_report(report)

    assert str(report.title) == "SugarSubstitute crashed"
    assert report.operation_context is not None
    assert report.operation_context.trace_id == "incident-1"
    assert report.operation_context.values["exit_code"] == -1073741819
    assert report.operation_context.values["attachments"] == ("minidump.dmp",)
    assert "frame one" in rendered
    assert "EXCEPTION_ACCESS_VIOLATION" in rendered


def test_unclean_termination_is_not_falsely_labeled_a_crash() -> None:
    """Missing clean receipts alone should produce accurate attribution wording."""

    incident = CrashIncident(
        incident_id="incident-2",
        run_id="run-2",
        occurred_at_utc="2026-08-31T12:00:00+00:00",
        kind=CrashKind.ABNORMAL_EXIT,
        boundary=CrashBoundary.SUPERVISOR,
        attribution=CrashAttribution.UNCLEAN_TERMINATION,
        summary="Missing clean shutdown receipt",
        process_id=42,
        exit_code=0,
    )

    report = build_crash_error_report(incident)

    assert str(report.title) == "SugarSubstitute did not close normally"
