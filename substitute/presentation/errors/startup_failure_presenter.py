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

"""Present blocking startup failures in an independently owned Fluent window."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.error_report_window import (
    SharedErrorReportWindow,
)
from sugarsubstitute_shared.presentation.localization import (
    render_application_text,
    set_localized_window_title,
)
from substitute.application.error_report_builder import ErrorReportBuilder
from substitute.application.errors import ErrorReport
from substitute.presentation.dialogs.error_report_presentation import (
    build_error_report_presentation,
)


def present_startup_failure_report(report: ErrorReport) -> None:
    """Own one report window whose native close also ends the blocking lifetime."""
    report_text = ErrorReportBuilder(text_renderer=render_application_text).render(
        report
    )
    window = SharedErrorReportWindow(
        presentation=build_error_report_presentation(report, report_text),
    )
    set_localized_window_title(window, "ComfyUI startup failed")
    try:
        window.exec()
    finally:
        window.close()
        window.deleteLater()


__all__ = ["present_startup_failure_report"]
