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

"""Open the trusted issue tracker carried by a structured error report."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from substitute.application.errors import ErrorReport


_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ErrorReportIssueAction:
    """Open one explicitly supplied trusted issue-tracker URL."""

    issues_url: str

    @classmethod
    def from_report(cls, report: ErrorReport) -> ErrorReportIssueAction | None:
        """Resolve an issue action from explicit operation context."""

        context = report.operation_context
        if context is None:
            return None
        issues_url = context.values.get("issues_url")
        if not isinstance(issues_url, str) or not issues_url:
            return None
        return cls(issues_url=issues_url)

    def open(self) -> None:
        """Open the issue tracker without changing modal state."""

        if not _open_external_url(self.issues_url):
            _LOG.warning(
                "Failed to open error report issue tracker.",
                extra={"url": self.issues_url},
            )


def _open_external_url(url: str) -> bool:
    """Open a trusted report URL through the desktop shell."""

    return bool(QDesktopServices.openUrl(QUrl(url)))


__all__ = ["ErrorReportIssueAction"]
