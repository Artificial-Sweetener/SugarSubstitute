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

"""Route onboarding failures through the application's copyable error surface."""

from __future__ import annotations

from pathlib import Path

from sugarsubstitute_shared.crash_reporting.redaction import CrashReportRedactor
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.errors import (
    DiagnosticSeverity,
    ErrorReport,
    ErrorReportKind,
    RuntimeReportContext,
    SubstituteOperationContext,
)
from substitute.application.onboarding import OnboardingProvisioningFailure
from substitute.presentation.errors.error_presenter import (
    ErrorReportPresenterProtocol,
)


class OnboardingFailurePresenter:
    """Build a redacted setup report and delegate its modal presentation."""

    def __init__(
        self,
        *,
        report_presenter: ErrorReportPresenterProtocol,
        installation_root: Path,
    ) -> None:
        """Store the shared report surface and identifying-path redactor."""

        self._report_presenter = report_presenter
        self._redactor = CrashReportRedactor(
            home=Path.home(),
            install_root=installation_root,
        )

    def present(
        self,
        failure: OnboardingProvisioningFailure,
        *,
        log_tail: str = "",
    ) -> None:
        """Show one redacted, copyable onboarding setup report."""

        detail_parts = [failure.technical_detail]
        if failure.remediation_steps:
            detail_parts.extend(
                (
                    "Recovery:",
                    *(
                        f"- {render_application_text(step)}"
                        for step in failure.remediation_steps
                    ),
                )
            )
        if log_tail.strip():
            detail_parts.extend(("Setup log tail:", log_tail.strip()))
        self._report_presenter.show_error_report(
            ErrorReport(
                kind=ErrorReportKind.SUBSTITUTE_INTERNAL,
                severity=DiagnosticSeverity.ERROR,
                title=failure.headline,
                message=failure.user_message,
                stage="onboarding_setup",
                exception_type=type(failure).__name__,
                technical_detail=self._redactor.text("\n".join(detail_parts)),
                operation_context=SubstituteOperationContext(
                    operation="onboarding_setup",
                    trace_id=failure.transaction_id,
                    values={
                        "failed_task": failure.failed_task or "unknown",
                    },
                ),
                runtime=RuntimeReportContext(launch_args=()),
            )
        )


__all__ = ["OnboardingFailurePresenter"]
