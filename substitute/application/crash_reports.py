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

from sugarsubstitute_shared.crash_reporting import CrashAttribution, CrashIncident
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

    confirmed = incident.attribution is CrashAttribution.CONFIRMED
    title = (
        app_text("SugarSubstitute crashed")
        if confirmed
        else app_text("SugarSubstitute did not close normally")
    )
    message = (
        app_text(
            "Something unexpected stopped SugarSubstitute. You can copy this report "
            "and share it with the maintainers."
        )
        if confirmed
        else app_text(
            "The previous SugarSubstitute session ended without completing shutdown. "
            "The report below may help determine why."
        )
    )
    technical_detail = incident.exception_message or incident.summary
    return ErrorReport(
        kind=ErrorReportKind.SUBSTITUTE_INTERNAL,
        severity=DiagnosticSeverity.ERROR,
        title=title,
        message=message,
        stage=incident.boundary.value,
        exception_type=incident.exception_type,
        technical_detail=technical_detail,
        traceback=incident.traceback,
        operation_context=SubstituteOperationContext(
            operation="application_crash",
            trace_id=incident.incident_id,
            values={
                "incident_id": incident.incident_id,
                "run_id": incident.run_id,
                "crash_kind": incident.kind.value,
                "attribution": incident.attribution.value,
                "process_id": incident.process_id,
                "exit_code": incident.exit_code,
                "thread_name": incident.thread_name,
                "attachments": incident.attachments,
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
