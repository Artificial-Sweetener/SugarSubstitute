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

"""Present recoverable runtime issues for one editor panel."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)

from collections.abc import Mapping, Sequence
from typing import Protocol

from PySide6.QtWidgets import QWidget

from substitute.application.node_behavior import (
    LiveNodeDefinitionError,
    required_node_definition_requirements_for_editor_projection,
)
from substitute.application.workflows import (
    CubeRuntimeIssue,
    CubeRuntimeIssueSource,
    WorkflowIssueState,
    live_node_definition_error_to_cube_issues,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.runtime_issue_presenter")


class RuntimeIssueWidgetBuilderProtocol(Protocol):
    """Build runtime issue cube-section widgets for the panel host."""

    def build_error_cube_widget(
        self,
        route_key: str,
        *,
        issue_lines: tuple[str, ...],
    ) -> QWidget:
        """Build a passive cube section that displays runtime issues."""


class EditorPanelRuntimeIssueHost(Protocol):
    """Expose the panel state needed to project runtime issues."""

    _workflow_id: str | None
    _cube_states: Mapping[str, object] | None
    _stack_order: Sequence[str] | None
    _cube_section_builder: RuntimeIssueWidgetBuilderProtocol
    cube_sections: Mapping[str, object]


class EditorPanelRuntimeIssuePresenter:
    """Transform runtime issues into panel and cube-stack presentation."""

    def __init__(
        self,
        host: EditorPanelRuntimeIssueHost,
        *,
        workflow_issue_state: WorkflowIssueState | None = None,
    ) -> None:
        """Store collaborators for runtime issue projection."""

        self._host = host
        self._workflow_issue_state = workflow_issue_state or WorkflowIssueState()
        self._cube_runtime_issues: dict[str, tuple[CubeRuntimeIssue, ...]] = {}

    def register_projection_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
        source: CubeRuntimeIssueSource,
    ) -> bool:
        """Register missing projection metadata against saved cube nodes."""

        workflow_id = self._workflow_id()
        cube_states = getattr(self._host, "_cube_states", None) or {}
        buffers = {
            alias: buffer
            for alias, state in cube_states.items()
            if isinstance(buffer := getattr(state, "buffer", None), Mapping)
        }
        issues = live_node_definition_error_to_cube_issues(
            error,
            workflow_id=workflow_id,
            source=source,
            requirements=required_node_definition_requirements_for_editor_projection(
                buffers
            ),
        )
        covered_classes = {
            class_type for issue in issues for class_type in issue.missing_node_classes
        }
        covered_fields = {field for issue in issues for field in issue.missing_fields}
        if (
            not issues
            or set(_missing_live_node_classes(error)) - covered_classes
            or set(_missing_live_node_fields(error)) - covered_fields
        ):
            log_warning(
                _LOGGER,
                "Editor projection blocked by unowned missing live node definitions",
                reason=reason,
                workflow_id=workflow_id,
                missing_node_classes=",".join(_missing_live_node_classes(error)),
                missing_fields=",".join(_missing_live_node_fields(error)),
            )
            return False
        self._workflow_issue_state.replace_projection_issues(
            workflow_id,
            issues,
            source,
        )
        self.sync_cube_runtime_issues_from_state()
        for issue in issues:
            log_warning(
                _LOGGER,
                "Registered cube runtime issue from live node definition failure",
                workflow_id=issue.workflow_id,
                cube_alias=issue.cube_alias,
                issue_kind=issue.kind.value,
                severity=issue.severity.value,
                missing_node_classes=issue.missing_node_classes,
                missing_fields=issue.missing_fields,
                node_names=issue.node_names,
                operation=issue.operation,
                recommended_action=issue.recommended_action,
                update_available=issue.update_candidate is not None,
                reason=reason,
            )
        return True

    def clear_projection_runtime_issues(self) -> None:
        """Clear projection-owned runtime issues after successful hydration."""

        self._workflow_issue_state.replace_projection_issues(
            self._workflow_id(),
            (),
            CubeRuntimeIssueSource.PROJECTION,
        )
        self.sync_cube_runtime_issues_from_state()

    def set_cube_runtime_issues(
        self,
        cube_alias: str,
        issues: Sequence[CubeRuntimeIssue],
    ) -> None:
        """Apply runtime issue presentation to one rendered cube section."""

        self._cube_runtime_issues[cube_alias] = tuple(issues)
        self.apply_cube_runtime_issues_to_widget(cube_alias)

    def clear_cube_runtime_issues(self, cube_alias: str) -> None:
        """Clear runtime issues for one cube and refresh its rendered section."""

        self._workflow_issue_state.clear_cube_issues(self._workflow_id(), cube_alias)
        self._cube_runtime_issues.pop(cube_alias, None)
        self.apply_cube_runtime_issues_to_widget(cube_alias)

    def cube_runtime_issues(
        self,
        cube_alias: str,
    ) -> tuple[CubeRuntimeIssue, ...]:
        """Return locally projected runtime issues for one cube."""

        return self._cube_runtime_issues.get(cube_alias, ())

    def cube_runtime_error_aliases(self) -> tuple[str, ...]:
        """Return aliases with error-severity runtime issues."""

        return tuple(
            sorted(
                alias
                for alias, issues in self._cube_runtime_issues.items()
                if any(issue.is_cube_scoped_error for issue in issues)
            )
        )

    def sync_cube_runtime_issues_from_state(self) -> None:
        """Refresh local issue projection from workflow-owned issue state."""

        workflow_id = self._workflow_id()
        aliases = set(self._cube_runtime_issues)
        stack_order = getattr(self._host, "_stack_order", None)
        if stack_order:
            aliases.update(stack_order)
        for alias in aliases:
            self._cube_runtime_issues[alias] = (
                self._workflow_issue_state.issues_for_cube(workflow_id, alias)
            )
            if not self._cube_runtime_issues[alias]:
                self._cube_runtime_issues.pop(alias, None)
            self.apply_cube_runtime_issues_to_widget(alias)

    def apply_cube_runtime_issues_to_widget(self, cube_alias: str) -> None:
        """Apply issue wash state to one cube section widget when it exists."""

        issues = self._cube_runtime_issues.get(cube_alias, ())
        severity = (
            "error" if any(issue.is_cube_scoped_error for issue in issues) else None
        )
        self.apply_cube_runtime_issues_to_stack(cube_alias, severity)
        cube_sections = getattr(self._host, "cube_sections", {})
        widget = cube_sections.get(cube_alias)
        if widget is None:
            return
        set_severity = getattr(widget, "setIssueSeverity", None)
        if callable(set_severity):
            set_severity(severity)
        set_messages = getattr(widget, "setIssueMessages", None)
        if callable(set_messages):
            set_messages(tuple(_issue_display_lines(issues)))

    def apply_cube_runtime_issues_to_stack(
        self,
        cube_alias: str,
        severity: str | None,
    ) -> None:
        """Apply issue severity to the matching cube-stack tab when available."""

        mainwindow = getattr(self._host, "mainwindow", None)
        cube_stacks = getattr(mainwindow, "cube_stacks", None)
        cube_stack = (
            cube_stacks.get(self._nullable_workflow_id())
            if isinstance(cube_stacks, Mapping)
            else None
        )
        set_issue = getattr(cube_stack, "setTabIssueSeverity", None)
        if callable(set_issue):
            set_issue(cube_alias, severity)

    def build_error_cube_widget(self, route_key: str, cube_state: object) -> QWidget:
        """Build a cube section that exposes recoverable runtime issues only."""

        del cube_state
        issues = self.cube_runtime_issues(route_key)
        return self._host._cube_section_builder.build_error_cube_widget(
            route_key,
            issue_lines=_issue_display_lines(issues),
        )

    def _workflow_id(self) -> str:
        """Return the host workflow ID as an issue-state key."""

        return self._nullable_workflow_id() or ""

    def _nullable_workflow_id(self) -> str | None:
        """Return the host workflow ID while preserving absence."""

        workflow_id = getattr(self._host, "_workflow_id", None)
        return workflow_id if workflow_id else None


def _missing_live_node_classes(error: LiveNodeDefinitionError) -> tuple[str, ...]:
    """Return unique missing live node classes from a metadata error."""

    return tuple(
        sorted(
            {
                item.class_type
                for item in error.missing_definitions
                if item.class_type.strip()
            }
        )
    )


def _missing_live_node_fields(error: LiveNodeDefinitionError) -> tuple[str, ...]:
    """Return unique missing live node fields from a metadata error."""

    return tuple(
        sorted(
            {
                f"{item.class_type}.{item.field_key}"
                for item in error.missing_fields
                if item.class_type.strip() and item.field_key.strip()
            }
        )
    )


def _issue_display_lines(issues: Sequence[CubeRuntimeIssue]) -> tuple[str, ...]:
    """Return concise display lines for cube runtime issues."""

    lines: list[str] = []
    for issue in issues:
        if issue.message:
            lines.append(render_application_text(issue.message))
        if issue.missing_node_classes:
            lines.extend(
                render_application_text(app_text("Missing definition: %1", class_type))
                for class_type in issue.missing_node_classes[:4]
            )
        if issue.missing_fields:
            lines.extend(
                render_application_text(app_text("Missing field: %1", field))
                for field in issue.missing_fields[:4]
            )
        if issue.recommended_action:
            lines.append(render_application_text(issue.recommended_action))
    return tuple(dict.fromkeys(lines))
