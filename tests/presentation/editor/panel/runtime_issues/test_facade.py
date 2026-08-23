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

"""Test runtime-issue presentation through the EditorPanel façade."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace

from substitute.application.workflows import (
    CubeRuntimeIssue,
    CubeRuntimeIssueKind,
    CubeRuntimeIssueSeverity,
    CubeRuntimeIssueSource,
)


class _IssueWidget:
    """Record issue severity and visible messages."""

    def __init__(self) -> None:
        """Initialize presentation state."""

        self.severity: str | None = None
        self.messages: tuple[str, ...] = ()

    def setIssueSeverity(self, severity: str | None) -> None:  # noqa: N802
        """Record severity presentation."""

        self.severity = severity

    def setIssueMessages(self, messages: tuple[str, ...]) -> None:  # noqa: N802
        """Record issue messages."""

        self.messages = messages


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_runtime_issue_presentation_applies_and_clears_widget_state() -> None:
    """Runtime issue presentation should update cube widgets and stack severity."""

    panel_module = _panel_module()
    issue_widget = _IssueWidget()
    stack_calls: list[tuple[str, str | None]] = []
    panel = SimpleNamespace(
        _workflow_id="workflow",
        _stack_order=["CubeA"],
        cube_sections={"CubeA": issue_widget},
        mainwindow=SimpleNamespace(
            cube_stacks={
                "workflow": SimpleNamespace(
                    setTabIssueSeverity=lambda alias, severity: stack_calls.append(
                        (alias, severity)
                    )
                )
            }
        ),
    )
    issue = CubeRuntimeIssue(
        workflow_id="workflow",
        cube_alias="CubeA",
        source=CubeRuntimeIssueSource.PROJECTION,
        severity=CubeRuntimeIssueSeverity.ERROR,
        kind=CubeRuntimeIssueKind.MISSING_LIVE_NODE_DEFINITION,
        message="Missing loader",
        operation="projection",
    )

    panel_module.EditorPanel.set_cube_runtime_issues(panel, "CubeA", (issue,))
    panel_module.EditorPanel.clear_cube_runtime_issues(panel, "CubeA")

    assert issue_widget.severity is None
    assert issue_widget.messages == ()
    assert stack_calls == [("CubeA", "error"), ("CubeA", None)]
