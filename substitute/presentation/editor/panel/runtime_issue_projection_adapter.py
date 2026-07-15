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

"""Adapt runtime issue state to projected widget build decisions."""

from __future__ import annotations

from typing import Protocol


class RuntimeIssueProjectionPanelPort(Protocol):
    """Describe panel error-widget construction used by runtime issue projection."""

    def _build_error_cube_widget(self, cube_alias: str, cube_state: object) -> object:
        """Build one cube widget that renders recoverable runtime issues."""


class RuntimeIssueProjectionIssuePort(Protocol):
    """Describe runtime issue lookup used during projected widget selection."""

    def is_errored_cube(self, cube_alias: str) -> bool:
        """Return whether the cube should render as an errored section."""


class RuntimeIssueProjectionPort(Protocol):
    """Describe runtime issue decisions required by projected widget building."""

    def should_replace_visible_widget_for_runtime_issue(
        self,
        cube_alias: str,
        widget: object,
    ) -> bool:
        """Return whether the visible widget no longer matches runtime issue state."""

    def build_error_widget_if_required(
        self,
        cube_alias: str,
        cube_state: object,
    ) -> object | None:
        """Build and return an error widget when runtime issues require one."""


class RuntimeIssueProjectionAdapter:
    """Own runtime issue widget decisions for projected editor cube builds."""

    def __init__(
        self,
        *,
        panel: RuntimeIssueProjectionPanelPort,
        runtime_issues: RuntimeIssueProjectionIssuePort,
    ) -> None:
        """Store runtime issue collaborators used by projected widget building."""

        self._panel = panel
        self._runtime_issues = runtime_issues

    def should_replace_visible_widget_for_runtime_issue(
        self,
        cube_alias: str,
        widget: object,
    ) -> bool:
        """Return whether the current widget must be replaced by an error widget."""

        if not self._runtime_issues.is_errored_cube(cube_alias):
            return False
        issue_severity = getattr(widget, "issueSeverity", None)
        current_severity = issue_severity() if callable(issue_severity) else None
        return current_severity != "error"

    def build_error_widget_if_required(
        self,
        cube_alias: str,
        cube_state: object,
    ) -> object | None:
        """Build an error widget when the cube has active runtime issues."""

        if not self._runtime_issues.is_errored_cube(cube_alias):
            return None
        return self._panel._build_error_cube_widget(cube_alias, cube_state)


__all__ = [
    "RuntimeIssueProjectionAdapter",
    "RuntimeIssueProjectionIssuePort",
    "RuntimeIssueProjectionPanelPort",
    "RuntimeIssueProjectionPort",
]
