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

"""Adapt application error reports to the shared QFluent report surface."""

from __future__ import annotations

from collections.abc import Callable

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.error_report_dialog import (
    ErrorReportPresentation,
    SharedErrorReportDialog,
)
from sugarsubstitute_shared.presentation.error_report_glyph import (
    ReportSeverity,
    ReportSeverityGlyphWidget,
)
from sugarsubstitute_shared.presentation.localization import render_application_text
from substitute.application.errors import (
    DiagnosticSeverity,
    ErrorReport,
    ErrorReportKind,
)
from substitute.presentation.dialogs.error_report_issue_action import (
    ErrorReportIssueAction,
)


class ErrorReportDialog(SharedErrorReportDialog):
    """Show one application report through the shared Fluent presentation."""

    def __init__(
        self,
        *,
        report: ErrorReport,
        report_text: str,
        open_console: Callable[[], None] | None = None,
        restart: Callable[[], None] | None = None,
        parent: object | None = None,
    ) -> None:
        """Adapt the app report model without duplicating presentation behavior."""

        self._report = report
        issue_action = ErrorReportIssueAction.from_report(report)
        super().__init__(
            presentation=ErrorReportPresentation(
                title=report.title,
                message=report.message,
                severity=_shared_severity(report.severity),
                summary_rows=_summary_rows(report),
                report_text=report_text,
                issue_action=issue_action.open if issue_action is not None else None,
                dismiss_on_mask=_is_update_rollback(report),
            ),
            open_console=open_console,
            restart=restart,
            parent=parent,
        )


def _summary_rows(report: ErrorReport) -> tuple[tuple[ApplicationText, str], ...]:
    """Project app-specific metadata into shared summary rows."""

    node = report.node
    rows: list[tuple[ApplicationText, str]] = [(app_text("Stage"), report.stage)]
    if not _is_update_rollback(report):
        rows.append(
            (
                app_text("Workflow"),
                report.workflow_id or render_application_text(app_text("unknown")),
            )
        )
    if report.prompt_id:
        rows.append((app_text("Prompt"), report.prompt_id))
    if node is not None:
        rows.append((app_text("Node"), _node_label(node.node_id, node.node_type)))
    if report.exception_type:
        rows.append((app_text("Exception"), report.exception_type))
    if report.kind is ErrorReportKind.PROMPT_VALIDATION:
        count = (
            len(report.prompt_validation.node_errors) if report.prompt_validation else 0
        )
        rows.append((app_text("Node errors"), str(count)))
    if report.kind is ErrorReportKind.CUBE_LIBRARY_DRIFT:
        rows.append((app_text("Affected cubes"), str(_affected_cube_count(report))))
    return tuple(rows)


def _shared_severity(severity: DiagnosticSeverity) -> ReportSeverity:
    """Map the application severity to the shared presentation contract."""

    if severity is DiagnosticSeverity.WARNING:
        return ReportSeverity.WARNING
    if severity is DiagnosticSeverity.INFO:
        return ReportSeverity.INFO
    return ReportSeverity.ERROR


def _node_label(node_id: str | None, node_type: str | None) -> str:
    """Return a compact node identity label."""

    if node_id and node_type:
        return f"{node_id} - {node_type}"
    return node_id or node_type or "unknown"


def _affected_cube_count(report: ErrorReport) -> int:
    """Return the Cube Library drift count from report operation context."""

    context = report.operation_context
    if context is None:
        return 0
    value = context.values.get("message_count")
    return value if isinstance(value, int) else 0


def _is_update_rollback(report: ErrorReport) -> bool:
    """Return whether compact update-specific summary behavior applies."""

    context = report.operation_context
    return context is not None and context.operation == "application_update"


__all__ = ["ErrorReportDialog", "ReportSeverityGlyphWidget"]
