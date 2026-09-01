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

"""Build and present a one-shot notice for a successfully rolled-back update."""

from __future__ import annotations

from typing import Protocol

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.issue_tracker import SUGARSUBSTITUTE_ISSUES_URL
from sugarsubstitute_shared.update_rollback_report import UpdateRollbackReport

from substitute._version import __version__
from substitute.application.errors import (
    DiagnosticSeverity,
    ErrorReport,
    ErrorReportKind,
    RuntimeReportContext,
    SubstituteOperationContext,
)


class UpdateRollbackReportRepository(Protocol):
    """Load and acknowledge the pending launcher rollback report."""

    def load(self) -> UpdateRollbackReport | None:
        """Return the pending report when one exists."""

    def acknowledge(self) -> None:
        """Remove the report after successful presentation."""


class UpdateRollbackErrorSink(Protocol):
    """Present one structured error report to the user."""

    def show_error_report(self, report: ErrorReport) -> None:
        """Show the report and return after the user dismisses it."""


class UpdateRollbackNoticeService:
    """Present and acknowledge one durable rolled-back update report."""

    def __init__(
        self,
        *,
        repository: UpdateRollbackReportRepository,
        error_sink: UpdateRollbackErrorSink,
    ) -> None:
        """Store the persistence and presentation ports."""

        self._repository = repository
        self._error_sink = error_sink

    def present_if_pending(self) -> bool:
        """Present one pending notice and acknowledge it after dismissal."""

        rollback = self._repository.load()
        if rollback is None:
            return False
        self._error_sink.show_error_report(build_update_rollback_error_report(rollback))
        self._repository.acknowledge()
        return True


def build_update_rollback_error_report(
    rollback: UpdateRollbackReport,
) -> ErrorReport:
    """Transform launcher diagnostics into the standard error-modal model."""

    traceback_lines = tuple(rollback.traceback.splitlines())
    return ErrorReport(
        kind=ErrorReportKind.SUBSTITUTE_INTERNAL,
        severity=DiagnosticSeverity.WARNING,
        title=app_text("Update failed"),
        message=app_text(
            "We tried to update Substitute, but it failed. Substitute is ready to "
            "use. Please send an error report to the maintainer."
        ),
        stage="update_rollback",
        exception_type=rollback.exception_type,
        technical_detail=rollback.traceback or rollback.message,
        traceback=traceback_lines,
        operation_context=SubstituteOperationContext(
            operation="application_update",
            values={
                "attempted_version": rollback.attempted_version,
                "failed_at_utc": rollback.occurred_at_utc,
                "failure_message": rollback.message,
                "issues_url": SUGARSUBSTITUTE_ISSUES_URL,
                "rollback_stage": rollback.stage.value,
            },
        ),
        runtime=RuntimeReportContext(substitute_version=__version__),
    )


__all__ = [
    "SUGARSUBSTITUTE_ISSUES_URL",
    "UpdateRollbackErrorSink",
    "UpdateRollbackNoticeService",
    "UpdateRollbackReportRepository",
    "build_update_rollback_error_report",
]
