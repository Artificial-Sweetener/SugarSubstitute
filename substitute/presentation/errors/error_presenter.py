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

"""Coordinate modal presentation for structured application error reports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from substitute.application.error_report_builder import ErrorReportBuilder
from substitute.application.errors import (
    ErrorReport,
    SubstituteOperationContext,
    build_comfy_connection_error_report,
    build_substitute_exception_report,
)


DialogFactory = Callable[
    [object | None, ErrorReport, str, Callable[[], None] | None], object
]


class ErrorReportPresenterProtocol(Protocol):
    """Describe the Substitute error presentation surface used by UI collaborators."""

    def show_error_report(self, report: ErrorReport) -> None:
        """Show a prepared structured error report."""

    def show_exception_report(
        self,
        *,
        title: str,
        message: str,
        stage: str,
        error: BaseException,
        context: SubstituteOperationContext,
    ) -> None:
        """Show a report for an exception raised by a direct user action."""

    def show_comfy_connection_report(
        self,
        *,
        title: str,
        message: str,
        stage: str,
        context: SubstituteOperationContext,
        error: BaseException | None = None,
    ) -> None:
        """Show a report for a Comfy connection/startup failure."""


@dataclass
class ErrorPresenter:
    """Present structured errors through Substitute's modal error surface."""

    parent: object | None = None
    open_console: Callable[[], None] | None = None
    report_builder: ErrorReportBuilder = field(default_factory=ErrorReportBuilder)
    dialog_factory: DialogFactory | None = None
    _active_report_keys: set[tuple[str, str, str | None, str | None]] = field(
        default_factory=set,
        init=False,
    )

    def show_error_report(self, report: ErrorReport) -> None:
        """Show a modal error report for a blocking or report-worthy failure."""

        report_key = (
            report.severity.value,
            report.kind.value,
            report.prompt_id,
            report.message,
        )
        if report_key in self._active_report_keys:
            return
        self._active_report_keys.add(report_key)
        report_text = self.report_builder.render(report)
        dialog = self._create_dialog(report, report_text)
        try:
            exec_method = getattr(dialog, "exec", None)
            if callable(exec_method):
                exec_method()
        finally:
            self._active_report_keys.discard(report_key)

    def show_exception_report(
        self,
        *,
        title: str,
        message: str,
        stage: str,
        error: BaseException,
        context: SubstituteOperationContext,
    ) -> None:
        """Build and show a Substitute exception report."""

        self.show_error_report(
            build_substitute_exception_report(
                title=title,
                message=message,
                stage=stage,
                error=error,
                context=context,
            )
        )

    def show_comfy_connection_report(
        self,
        *,
        title: str,
        message: str,
        stage: str,
        context: SubstituteOperationContext,
        error: BaseException | None = None,
    ) -> None:
        """Build and show a Comfy connection/startup report."""

        self.show_error_report(
            build_comfy_connection_error_report(
                title=title,
                message=message,
                stage=stage,
                error=error,
                context=context,
            )
        )

    def _create_dialog(self, report: ErrorReport, report_text: str) -> object:
        """Create the concrete qfluent error dialog lazily."""

        if self.dialog_factory is not None:
            return self.dialog_factory(
                self.parent,
                report,
                report_text,
                self.open_console,
            )
        from substitute.presentation.dialogs.error_report_dialog import (
            ErrorReportDialog,
        )

        return ErrorReportDialog(
            report=report,
            report_text=report_text,
            open_console=self.open_console,
            parent=self.parent,
        )


__all__ = ["ErrorPresenter", "ErrorReportPresenterProtocol"]
