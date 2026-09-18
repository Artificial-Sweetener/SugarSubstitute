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
from sugarsubstitute_shared.presentation.error_report_dialog import (
    SharedErrorReportDialog,
)
from sugarsubstitute_shared.presentation.error_report_glyph import (
    ReportSeverityGlyphWidget,
)
from substitute.application.errors import ErrorReport
from substitute.presentation.dialogs.error_report_presentation import (
    build_error_report_presentation,
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
        super().__init__(
            presentation=build_error_report_presentation(report, report_text),
            open_console=open_console,
            restart=restart,
            parent=parent,
        )


__all__ = ["ErrorReportDialog", "ReportSeverityGlyphWidget"]
