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

from substitute.application.errors import ErrorReport, render_error_report


class ErrorReportBuilder:
    """Build copyable plain-text reports from structured error facts."""

    def render(self, report: ErrorReport) -> str:
        """Return a deterministic plain-text report for one error."""

        return render_error_report(report)


__all__ = ["ErrorReportBuilder", "render_error_report"]
