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

"""Tests for editor-panel runtime issue presentation ownership."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.errors import SubstituteOperationContext
from substitute.application.node_behavior import (
    LiveNodeDefinitionError,
    MissingLiveNodeDefinition,
)
from substitute.application.workflows import (
    CubeRuntimeIssue,
    CubeRuntimeIssueKind,
    CubeRuntimeIssueSeverity,
    CubeRuntimeIssueSource,
    WorkflowIssueState,
)
from substitute.presentation.editor.panel.runtime_issue_presenter import (
    EditorPanelRuntimeIssueHost,
    EditorPanelRuntimeIssuePresenter,
)


class _IssueWidget:
    """Record issue presentation pushed to one cube section."""

    def __init__(self) -> None:
        """Initialize recorded issue presentation state."""

        self.severity: str | None = None
        self.messages: tuple[str, ...] = ()

    def setIssueSeverity(self, severity: str | None) -> None:  # noqa: N802
        """Record the requested issue severity."""

        self.severity = severity

    def setIssueMessages(self, messages: tuple[str, ...]) -> None:  # noqa: N802
        """Record the requested issue display messages."""

        self.messages = messages


class _CubeStack:
    """Record issue severity pushed to cube stack tabs."""

    def __init__(self) -> None:
        """Initialize recorded tab issue changes."""

        self.issue_severities: list[tuple[str, str | None]] = []

    def setTabIssueSeverity(
        self,
        cube_alias: str,
        severity: str | None,
    ) -> None:
        """Record the tab issue severity update."""

        self.issue_severities.append((cube_alias, severity))


class _MainWindow:
    """Expose cube stacks through the attribute used by the panel presenter."""

    def __init__(self, workflow_id: str, cube_stack: _CubeStack) -> None:
        """Initialize a workflow-to-stack registry."""

        self.cube_stacks: dict[str, _CubeStack] = {workflow_id: cube_stack}


class _Builder:
    """Record runtime issue widget build requests."""

    def __init__(self) -> None:
        """Initialize build call recording."""

        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def build_error_cube_widget(
        self,
        route_key: str,
        *,
        issue_lines: tuple[str, ...],
    ) -> QWidget:
        """Record build inputs and return a placeholder Qt widget."""

        self.calls.append((route_key, issue_lines))
        return QWidget()


class _Host:
    """Provide the presenter-facing subset of editor panel state."""

    def __init__(
        self,
        *,
        workflow_id: str = "workflow-a",
        stack_order: tuple[str, ...] | None = ("CubeA",),
    ) -> None:
        """Initialize host state with one cube section and cube stack."""

        self._workflow_id: str | None = workflow_id
        self._stack_order: tuple[str, ...] | None = stack_order
        self.cube_sections: dict[str, _IssueWidget] = {"CubeA": _IssueWidget()}
        self._cube_section_builder = _Builder()
        self.cube_stack = _CubeStack()
        self.mainwindow = _MainWindow(workflow_id, self.cube_stack)


class _RecordingErrorPresenter:
    """Record structured error reports requested by the runtime issue presenter."""

    def __init__(self) -> None:
        """Initialize the recorded call list."""

        self.comfy_reports: list[dict[str, object]] = []

    def show_error_report(self, report: object) -> None:
        """Record a prepared report when a caller uses the generic surface."""

        self.comfy_reports.append({"report": report})

    def show_exception_report(
        self,
        *,
        title: str,
        message: str,
        stage: str,
        error: BaseException,
        context: SubstituteOperationContext,
    ) -> None:
        """Record an exception report when a caller uses the exception surface."""

        self.comfy_reports.append(
            {
                "title": title,
                "message": message,
                "stage": stage,
                "error": error,
                "context": context,
            }
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
        """Record the Comfy metadata report shown by the presenter."""

        self.comfy_reports.append(
            {
                "title": title,
                "message": message,
                "stage": stage,
                "error": error,
                "context": context,
            }
        )


def _ensure_qapp() -> QApplication:
    """Return the shared QApplication used by presenter widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _missing_live_node_error(
    *,
    cube_aliases: tuple[str, ...] = ("CubeA",),
    node_names: tuple[str, ...] = ("detailer",),
) -> LiveNodeDefinitionError:
    """Build a live-node definition error for presenter tests."""

    return LiveNodeDefinitionError(
        operation="hydrate editor projection node definitions",
        missing_definitions=(
            MissingLiveNodeDefinition(
                class_type="SimpleSyrup.DetailSEGSByScaleFactor",
                cube_aliases=cube_aliases,
                node_names=node_names,
            ),
        ),
    )


def _runtime_issue(
    *,
    severity: CubeRuntimeIssueSeverity = CubeRuntimeIssueSeverity.ERROR,
    source: CubeRuntimeIssueSource = CubeRuntimeIssueSource.PROJECTION,
) -> CubeRuntimeIssue:
    """Build a deterministic cube runtime issue for presenter tests."""

    return CubeRuntimeIssue(
        workflow_id="workflow-a",
        cube_alias="CubeA",
        severity=severity,
        kind=CubeRuntimeIssueKind.MISSING_LIVE_NODE_DEFINITION,
        message="Runtime issue",
        operation="test operation",
        source=source,
        missing_node_classes=("SimpleSyrup.DetailSEGSByScaleFactor",),
        node_names=("detailer",),
        recommended_action="Restart ComfyUI.",
    )


def test_register_projection_live_node_definition_error_projects_cube_issue() -> None:
    """Cube-attributed live-node errors update state, section, and stack display."""

    _ensure_qapp()
    issue_state = WorkflowIssueState()
    host = _Host()
    presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, host),
        workflow_issue_state=issue_state,
    )

    handled = presenter.register_projection_live_node_definition_error(
        _missing_live_node_error(),
        reason="projection_refresh",
        source=CubeRuntimeIssueSource.PROJECTION,
    )

    assert handled is True
    issues = presenter.cube_runtime_issues("CubeA")
    assert issues == issue_state.issues_for_cube("workflow-a", "CubeA")
    assert issues[0].missing_node_classes == ("SimpleSyrup.DetailSEGSByScaleFactor",)
    assert host.cube_sections["CubeA"].severity == "error"
    assert "Missing definition: SimpleSyrup.DetailSEGSByScaleFactor" in (
        host.cube_sections["CubeA"].messages
    )
    assert host.cube_stack.issue_severities[-1] == ("CubeA", "error")


def test_register_projection_live_node_definition_error_rejects_unowned_error() -> None:
    """Unowned live-node errors stay fatal instead of becoming inline cube issues."""

    issue_state = WorkflowIssueState()
    host = _Host()
    presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, host),
        workflow_issue_state=issue_state,
    )

    handled = presenter.register_projection_live_node_definition_error(
        _missing_live_node_error(cube_aliases=()),
        reason="projection_refresh",
        source=CubeRuntimeIssueSource.PROJECTION,
    )

    assert handled is False
    assert presenter.cube_runtime_issues("CubeA") == ()
    assert issue_state.issues_for_cube("workflow-a", "CubeA") == ()
    assert host.cube_sections["CubeA"].severity is None
    assert host.cube_stack.issue_severities == []


def test_recoverable_live_node_definition_report_dedupes_until_projection_reset() -> (
    None
):
    """Recoverable reports are suppressed within one projection window only."""

    error_presenter = _RecordingErrorPresenter()
    host = _Host()
    presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, host),
        error_presenter=error_presenter,
    )
    error = _missing_live_node_error()

    presenter.present_recoverable_live_node_definition_error(
        error,
        reason="projection_refresh",
    )
    presenter.present_recoverable_live_node_definition_error(
        error,
        reason="projection_refresh",
    )
    presenter.begin_live_node_definition_report_projection()
    presenter.present_recoverable_live_node_definition_error(
        error,
        reason="projection_refresh",
    )

    assert len(error_presenter.comfy_reports) == 2
    first_context = cast(
        SubstituteOperationContext,
        error_presenter.comfy_reports[0]["context"],
    )
    assert first_context.values["cube_aliases"] == ("CubeA",)
    assert first_context.values["node_names"] == ("detailer",)


def test_clear_projection_runtime_issues_preserves_other_sources() -> None:
    """Clearing projection issues leaves non-projection runtime issues displayed."""

    issue_state = WorkflowIssueState()
    projection_issue = _runtime_issue(source=CubeRuntimeIssueSource.PROJECTION)
    library_issue = _runtime_issue(source=CubeRuntimeIssueSource.CUBE_LIBRARY)
    issue_state.add_issues((projection_issue, library_issue))
    host = _Host()
    presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, host),
        workflow_issue_state=issue_state,
    )
    presenter.sync_cube_runtime_issues_from_state()

    presenter.clear_projection_runtime_issues()

    assert presenter.cube_runtime_issues("CubeA") == (library_issue,)
    assert issue_state.issues_for_cube("workflow-a", "CubeA") == (library_issue,)
    assert host.cube_sections["CubeA"].severity == "error"


def test_set_and_clear_cube_runtime_issues_updates_widget_and_stack() -> None:
    """Direct cube issue projection updates both section and stack state."""

    host = _Host()
    presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, host)
    )

    presenter.set_cube_runtime_issues("CubeA", (_runtime_issue(),))
    presenter.clear_cube_runtime_issues("CubeA")

    assert presenter.cube_runtime_issues("CubeA") == ()
    assert host.cube_sections["CubeA"].messages == ()
    assert host.cube_sections["CubeA"].severity is None
    assert host.cube_stack.issue_severities == [
        ("CubeA", "error"),
        ("CubeA", None),
    ]


def test_cube_runtime_error_aliases_ignores_warnings() -> None:
    """Only error-severity runtime issues participate in blocked alias detection."""

    host = _Host()
    presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, host)
    )

    presenter.set_cube_runtime_issues(
        "CubeA",
        (_runtime_issue(severity=CubeRuntimeIssueSeverity.WARNING),),
    )

    assert presenter.cube_runtime_error_aliases() == ()


def test_build_error_cube_widget_passes_current_issues_to_builder() -> None:
    """Error cube widgets receive the presenter's current issue display lines."""

    _ensure_qapp()
    cube_state = object()
    host = _Host()
    presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, host)
    )
    issue = _runtime_issue()
    presenter.set_cube_runtime_issues("CubeA", (issue,))

    widget = presenter.build_error_cube_widget("CubeA", cube_state)

    assert isinstance(widget, QWidget)
    assert host._cube_section_builder.calls == [
        (
            "CubeA",
            (
                issue.message,
                "Missing definition: SimpleSyrup.DetailSEGSByScaleFactor",
                issue.recommended_action,
            ),
        )
    ]
