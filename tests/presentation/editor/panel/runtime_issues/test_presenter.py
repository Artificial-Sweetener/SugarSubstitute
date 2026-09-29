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

from types import SimpleNamespace
from typing import cast

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from substitute.application.node_behavior import (
    DegradedNodeBehavior,
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
from substitute.presentation.editor.panel.widgets.cube_section import CubeSectionView
from substitute.presentation.editor.panel.widgets.cube_section_overlays import (
    CubeSectionIssueOverlay,
)
from substitute.presentation.editor.panel.widgets.degraded_node_card import (
    build_degraded_node_card,
)
from substitute.presentation.editor.panel.widgets.masonry_grid_layout import (
    MasonryGridLayout,
)
from tests.support.qt.lifecycle import destroy_qt_object


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
        self._cube_states: dict[str, object] | None = None
        self._stack_order: tuple[str, ...] | None = stack_order
        self.cube_sections: dict[str, _IssueWidget] = {"CubeA": _IssueWidget()}
        self._cube_section_builder = _Builder()
        self.cube_stack = _CubeStack()
        self.mainwindow = _MainWindow(workflow_id, self.cube_stack)


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
    kind: CubeRuntimeIssueKind = CubeRuntimeIssueKind.MISSING_LIVE_NODE_DEFINITION,
    node_names: tuple[str, ...] = ("detailer",),
) -> CubeRuntimeIssue:
    """Build a deterministic cube runtime issue for presenter tests."""

    return CubeRuntimeIssue(
        workflow_id="workflow-a",
        cube_alias="CubeA",
        severity=severity,
        kind=kind,
        message="Runtime issue",
        operation="test operation",
        source=source,
        missing_node_classes=("SimpleSyrup.DetailSEGSByScaleFactor",),
        node_names=node_names,
        recommended_action="Restart ComfyUI.",
    )


def test_register_projection_live_node_definition_error_projects_cube_issue() -> None:
    """A missing node stays in issue state without washing its healthy cube."""

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
    assert host.cube_sections["CubeA"].severity is None
    assert "Missing definition: SimpleSyrup.DetailSEGSByScaleFactor" in (
        host.cube_sections["CubeA"].messages
    )
    assert host.cube_stack.issue_severities[-1] == ("CubeA", None)


def test_register_projection_live_node_definition_error_attributes_saved_node() -> None:
    """A missing class without supplied aliases still marks its saved cube node."""

    issue_state = WorkflowIssueState()
    host = _Host()
    host._cube_states = {
        "CubeA": SimpleNamespace(
            buffer={
                "nodes": {
                    "detailer": {
                        "class_type": "SimpleSyrup.DetailSEGSByScaleFactor",
                        "inputs": {},
                    }
                }
            }
        )
    }
    presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, host),
        workflow_issue_state=issue_state,
    )

    handled = presenter.register_projection_live_node_definition_error(
        _missing_live_node_error(cube_aliases=()),
        reason="projection_refresh",
        source=CubeRuntimeIssueSource.PROJECTION,
    )

    assert handled is True
    assert presenter.cube_runtime_issues("CubeA")[0].node_names == ("detailer",)
    assert presenter.cube_runtime_error_aliases() == ()
    assert issue_state.issues_for_cube("workflow-a", "CubeA")
    assert host.cube_sections["CubeA"].severity is None
    assert host.cube_stack.issue_severities[-1] == ("CubeA", None)


def test_cube_attributed_metadata_failure_stays_inline_without_modal() -> None:
    """An attributed missing node belongs to its cube, not a modal report."""

    host = _Host()
    presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, host),
    )
    error = _missing_live_node_error()

    handled = presenter.register_projection_live_node_definition_error(
        error,
        reason="projection_refresh",
        source=CubeRuntimeIssueSource.PROJECTION,
    )

    assert handled
    assert presenter.cube_runtime_issues("CubeA")


def test_clear_projection_runtime_issues_preserves_other_sources() -> None:
    """Clearing projection issues leaves non-projection runtime issues displayed."""

    issue_state = WorkflowIssueState()
    projection_issue = _runtime_issue(source=CubeRuntimeIssueSource.PROJECTION)
    library_issue = _runtime_issue(
        source=CubeRuntimeIssueSource.CUBE_LIBRARY,
        kind=CubeRuntimeIssueKind.PROJECTION_HYDRATION_FAILED,
        node_names=(),
    )
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

    presenter.set_cube_runtime_issues(
        "CubeA",
        (_runtime_issue(kind=CubeRuntimeIssueKind.PROJECTION_HYDRATION_FAILED),),
    )
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


def test_cube_runtime_error_aliases_preserves_node_scoped_projection() -> None:
    """A node-scoped definition issue should not wash or replace its cube."""

    host = _Host()
    presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, host)
    )

    presenter.set_cube_runtime_issues("CubeA", (_runtime_issue(),))

    assert presenter.cube_runtime_error_aliases() == ()
    assert host.cube_sections["CubeA"].severity is None
    assert host.cube_stack.issue_severities[-1] == ("CubeA", None)


def test_missing_node_only_washes_its_card_in_real_cube_section() -> None:
    """A node failure clears cube overlay while retaining its degraded card."""

    app = _ensure_qapp()
    grid = MasonryGridLayout()
    healthy_card = QWidget()
    healthy_card.setObjectName("HealthyNodeCard")
    grid.addWidget(healthy_card)
    degraded_card = build_degraded_node_card(
        DegradedNodeBehavior(
            node_name="detailer",
            class_type="SimpleSyrup.DetailSEGSByScaleFactor",
            title="Detailer",
            missing_definition_classes=("SimpleSyrup.DetailSEGSByScaleFactor",),
        )
    )
    grid.addWidget(degraded_card)
    section = CubeSectionView(
        header_bar=QWidget(),
        prompt_area=QVBoxLayout(),
        grid_layout=grid,
    )
    host = _Host()
    host.cube_sections["CubeA"] = cast(_IssueWidget, section)
    presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, host)
    )
    try:
        section.show()
        app.processEvents()
        overlay = section.findChild(CubeSectionIssueOverlay)
        assert overlay is not None

        presenter.set_cube_runtime_issues(
            "CubeA",
            (_runtime_issue(kind=CubeRuntimeIssueKind.PROJECTION_HYDRATION_FAILED),),
        )
        assert section.issueSeverity() == "error"
        assert overlay.isVisible()

        presenter.set_cube_runtime_issues("CubeA", (_runtime_issue(),))
        assert section.issueSeverity() is None
        assert not overlay.isVisible()
        assert healthy_card.objectName() == "HealthyNodeCard"
        assert degraded_card.objectName() == "DegradedNodeCard"
        assert healthy_card.isVisible()
        assert degraded_card.isVisible()
    finally:
        section.close()
        destroy_qt_object(section)


def test_cube_runtime_error_aliases_keeps_unscoped_failures_blocking() -> None:
    """A non-node-scoped projection failure should still replace the cube."""

    host = _Host()
    presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, host)
    )

    presenter.set_cube_runtime_issues(
        "CubeA",
        (
            _runtime_issue(
                kind=CubeRuntimeIssueKind.PROJECTION_HYDRATION_FAILED,
                node_names=(),
            ),
        ),
    )

    assert presenter.cube_runtime_error_aliases() == ("CubeA",)


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
