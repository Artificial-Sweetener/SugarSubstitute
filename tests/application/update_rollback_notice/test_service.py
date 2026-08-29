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

"""Verify one-shot presentation of successfully rolled-back updates."""

from __future__ import annotations

from dataclasses import dataclass, field
import pytest

from sugarsubstitute_shared.update_rollback_report import (
    UpdateRollbackReport,
    UpdateRollbackStage,
)

from substitute.application.errors import (
    DiagnosticSeverity,
    ErrorReport,
    ErrorReportKind,
)
from substitute.application.update_rollback_notice import (
    SUGARSUBSTITUTE_ISSUES_URL,
    UpdateRollbackNoticeService,
)


@dataclass
class _Repository:
    """Hold one report and record acknowledgement."""

    report: UpdateRollbackReport | None
    acknowledged: bool = False

    def load(self) -> UpdateRollbackReport | None:
        """Return the configured report."""

        return self.report

    def acknowledge(self) -> None:
        """Record successful user presentation."""

        self.acknowledged = True


@dataclass
class _Sink:
    """Capture structured reports shown through the modal system."""

    reports: list[ErrorReport] = field(default_factory=list)

    def show_error_report(self, report: ErrorReport) -> None:
        """Capture one report after the modal would be dismissed."""

        self.reports.append(report)


def test_notice_presents_compact_report_and_acknowledges_after_dismissal() -> None:
    """A restored app should show the standard report exactly once."""

    repository = _Repository(
        UpdateRollbackReport(
            attempted_version="0.21.3",
            stage=UpdateRollbackStage.CANDIDATE_READINESS,
            exception_type="ApplicationReadinessError",
            message="candidate did not become ready",
            traceback="Traceback\nApplicationReadinessError: candidate did not become ready",
            occurred_at_utc="2026-08-29T02:09:03Z",
        )
    )
    sink = _Sink()

    presented = UpdateRollbackNoticeService(
        repository=repository,
        error_sink=sink,
    ).present_if_pending()

    assert presented is True
    assert repository.acknowledged is True
    assert len(sink.reports) == 1
    report = sink.reports[0]
    assert report.kind is ErrorReportKind.SUBSTITUTE_INTERNAL
    assert report.severity is DiagnosticSeverity.WARNING
    assert report.operation_context is not None
    assert report.operation_context.values["attempted_version"] == "0.21.3"
    assert report.operation_context.values["issues_url"] == SUGARSUBSTITUTE_ISSUES_URL


def test_notice_preserves_report_when_presentation_fails() -> None:
    """Do not acknowledge diagnostics that never reached the user."""

    repository = _Repository(
        UpdateRollbackReport(
            attempted_version="0.21.3",
            stage=UpdateRollbackStage.PREPARATION,
            exception_type="RuntimeError",
            message="runtime repair failed",
            traceback="RuntimeError: runtime repair failed",
            occurred_at_utc="2026-08-29T02:09:03Z",
        )
    )

    class _FailingSink:
        """Reject presentation to exercise acknowledgement ordering."""

        def show_error_report(self, _report: ErrorReport) -> None:
            """Raise before dismissal can occur."""

            raise RuntimeError("modal unavailable")

    with pytest.raises(RuntimeError, match="modal unavailable"):
        UpdateRollbackNoticeService(
            repository=repository,
            error_sink=_FailingSink(),
        ).present_if_pending()

    assert repository.acknowledged is False
