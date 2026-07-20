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

"""Render structured application error reports for display and copy actions."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.errors import (
    ErrorReport,
    ReportTextRenderer,
    render_error_report,
)


@dataclass(frozen=True, slots=True)
class ErrorReportBuilder:
    """Build copyable plain-text reports from structured error facts."""

    text_renderer: ReportTextRenderer | None = None

    def render(self, report: ErrorReport) -> str:
        """Return a deterministic plain-text report for one error."""

        if self.text_renderer is None:
            return render_error_report(report)
        return render_error_report(report, self.text_renderer)


__all__ = ["ErrorReportBuilder", "render_error_report"]
