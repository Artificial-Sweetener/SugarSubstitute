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

"""Transform durable crash incidents into the standard error-report contract."""

from __future__ import annotations

from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashIncident,
    CrashKind,
)
from sugarsubstitute_shared.issue_tracker import SUGARSUBSTITUTE_ISSUES_URL
from sugarsubstitute_shared.localization import app_text

from substitute.application.errors import (
    DiagnosticSeverity,
    ErrorReport,
    ErrorReportKind,
    RuntimeReportContext,
    SubstituteOperationContext,
)


def build_crash_error_report(incident: CrashIncident) -> ErrorReport:
    """Project one crash incident into the existing user-visible report model."""

    startup_failure = incident.kind is CrashKind.STARTUP
    confirmed = incident.attribution is CrashAttribution.CONFIRMED
    if startup_failure:
        title = app_text("SugarSubstitute could not finish starting")
        message = app_text(
            "SugarSubstitute encountered a confirmed startup failure. Copy this "
            "report and share it with the maintainers."
        )
    elif confirmed:
        title = app_text("SugarSubstitute crashed")
        message = app_text(
            "Something unexpected stopped SugarSubstitute. You can copy this report "
            "and share it with the maintainers."
        )
    else:
        title = app_text("SugarSubstitute did not close normally")
        message = app_text(
            "The previous SugarSubstitute session ended without completing shutdown. "
            "The report below may help determine why."
        )
    technical_detail = incident.exception_message or incident.summary
    return ErrorReport(
        kind=(
            ErrorReportKind.APPLICATION_LIFECYCLE
            if startup_failure or not confirmed
            else ErrorReportKind.SUBSTITUTE_INTERNAL
        ),
        severity=DiagnosticSeverity.ERROR,
        title=title,
        message=message,
        stage=incident.boundary.value,
        exception_type=incident.exception_type,
        technical_detail=technical_detail,
        traceback=incident.traceback,
        operation_context=SubstituteOperationContext(
            operation=(
                "application_startup" if startup_failure else "application_crash"
            ),
            trace_id=incident.incident_id,
            values={
                "incident_id": incident.incident_id,
                "run_id": incident.run_id,
                "occurred_at_utc": incident.occurred_at_utc,
                "crash_kind": incident.kind.value,
                "attribution": incident.attribution.value,
                "process_id": incident.process_id,
                "exit_code": incident.exit_code,
                "thread_name": incident.thread_name,
                "attachments": incident.attachments,
                **incident.metadata,
                "issues_url": SUGARSUBSTITUTE_ISSUES_URL,
            },
        ),
        runtime=RuntimeReportContext(
            substitute_version=incident.application_version,
            os_name=incident.platform,
            python_version=incident.python_version,
            launch_args=incident.launch_arguments,
        ),
    )


__all__ = ["build_crash_error_report"]
