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

"""Present launcher installation failures through the shared report dialog."""

from __future__ import annotations

import platform

from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from sugarsubstitute_shared.presentation.error_report_dialog import (
    ErrorReportPresentation,
    SharedErrorReportDialog,
)
from sugarsubstitute_shared.presentation.error_report_glyph import ReportSeverity


class InstallerFailurePresenter:
    """Own the launcher's copyable, nonblocking error-report surface."""

    def __init__(self, parent: QWidget) -> None:
        """Retain the installer window that the modal must fully cover."""

        self._parent = parent
        self._dialog: SharedErrorReportDialog | None = None

    @property
    def active_dialog(self) -> SharedErrorReportDialog | None:
        """Return the currently visible report dialog for qualification."""

        return self._dialog

    def show_failure(self, *, stage: str, details: str) -> None:
        """Show one actionable report whose full diagnostics can be copied."""

        if self._dialog is not None and isValid(self._dialog):
            self._dialog.hide()
            self._dialog.close()
            self._dialog.deleteLater()
        title = launcher_text("Setup could not continue")
        message = launcher_text(
            "Nothing else was changed. Review the report, then try this step again."
        )
        report_text = "\n".join(
            (
                title,
                "",
                launcher_text("Stage: %1", stage),
                launcher_text("Platform: %1", platform.platform()),
                "",
                launcher_text("Technical details:"),
                details,
            )
        )
        self._dialog = SharedErrorReportDialog(
            presentation=ErrorReportPresentation(
                title=title,
                message=message,
                severity=ReportSeverity.ERROR,
                summary_rows=((launcher_text("Stage"), stage),),
                report_text=report_text,
            ),
            parent=self._parent,
        )
        self._dialog.show()
        self._dialog.raise_()


__all__ = ["InstallerFailurePresenter"]
