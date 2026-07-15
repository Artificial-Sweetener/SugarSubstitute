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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from PySide6.QtWidgets import QWidget

from substitute.application.errors import SubstituteOperationContext
from substitute.application.node_behavior import LiveNodeDefinitionError
from substitute.application.workflows import (
    CubeRuntimeIssue,
    CubeRuntimeIssueSeverity,
    CubeRuntimeIssueSource,
    WorkflowIssueState,
    live_node_definition_error_to_cube_issues,
)
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

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
    _stack_order: Sequence[str] | None
    _cube_section_builder: RuntimeIssueWidgetBuilderProtocol
    cube_sections: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class LiveNodeDefinitionReportFingerprint:
    """Identify one user-visible live metadata report for deduplication."""

    workflow_id: str
    reason: str
    operation: str
    missing_node_classes: tuple[str, ...]
    missing_fields: tuple[str, ...]
    cube_aliases: tuple[str, ...]
    node_names: tuple[str, ...]


class EditorPanelRuntimeIssuePresenter:
    """Transform runtime issues into panel, tab, and error-report presentation."""

    def __init__(
        self,
        host: EditorPanelRuntimeIssueHost,
        *,
        workflow_issue_state: WorkflowIssueState | None = None,
        error_presenter: ErrorReportPresenterProtocol | None = None,
    ) -> None:
        """Store collaborators for runtime issue projection."""

        self._host = host
        self._error_presenter = error_presenter
        self._workflow_issue_state = workflow_issue_state or WorkflowIssueState()
        self._cube_runtime_issues: dict[str, tuple[CubeRuntimeIssue, ...]] = {}
        self._shown_live_node_definition_report_fingerprints: set[
            LiveNodeDefinitionReportFingerprint
        ] = set()

    def begin_live_node_definition_report_projection(self) -> None:
        """Start a projection-scoped live metadata report dedupe window."""

        self._shown_live_node_definition_report_fingerprints.clear()

    def register_projection_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
        source: CubeRuntimeIssueSource,
    ) -> bool:
        """Register a cube-attributed projection hydration failure."""

        workflow_id = self._workflow_id()
        issues = live_node_definition_error_to_cube_issues(
            error,
            workflow_id=workflow_id,
            source=source,
        )
        if not issues or _has_unowned_live_node_definition_error(error):
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

    def present_recoverable_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
    ) -> None:
        """Show a deduplicated non-fatal live metadata report for a cube issue."""

        self.present_live_node_definition_error_once(error, reason=reason)

    def present_live_node_definition_error_once(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
    ) -> None:
        """Show one live metadata report unless the same report was already shown."""

        workflow_id = self._nullable_workflow_id()
        fingerprint = _live_node_definition_report_fingerprint(
            error,
            workflow_id=workflow_id,
            reason=reason,
        )
        if fingerprint in self._shown_live_node_definition_report_fingerprints:
            log_debug(
                _LOGGER,
                "Skipped duplicate recoverable live node definition report",
                workflow_id=workflow_id,
                reason=reason,
                missing_node_classes=",".join(fingerprint.missing_node_classes),
                cube_aliases=",".join(fingerprint.cube_aliases),
                node_names=",".join(fingerprint.node_names),
                operation=fingerprint.operation,
            )
            return
        self._shown_live_node_definition_report_fingerprints.add(fingerprint)
        self.present_live_node_definition_error(error, reason=reason)

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
                if any(
                    issue.severity == CubeRuntimeIssueSeverity.ERROR for issue in issues
                )
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
            "error"
            if any(issue.severity == CubeRuntimeIssueSeverity.ERROR for issue in issues)
            else None
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

    def present_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
    ) -> None:
        """Show the blocking live-metadata report through the injected presenter."""

        if self._error_presenter is None:
            log_warning(
                _LOGGER,
                "Cannot present live node definition error without error presenter",
                reason=reason,
                workflow_id=self._nullable_workflow_id(),
                missing_node_classes=",".join(_missing_live_node_classes(error)),
            )
            return
        self._error_presenter.show_comfy_connection_report(
            title="Live Comfy node definitions unavailable",
            message=_live_node_definition_error_message(error),
            stage="load_node_definitions",
            context=_live_node_definition_operation_context(
                error,
                workflow_id=self._nullable_workflow_id(),
                reason=reason,
            ),
            error=error,
        )

    def _workflow_id(self) -> str:
        """Return the host workflow ID as an issue-state key."""

        return self._nullable_workflow_id() or ""

    def _nullable_workflow_id(self) -> str | None:
        """Return the host workflow ID preserving absence for error reports."""

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


def _live_node_definition_error_message(error: LiveNodeDefinitionError) -> str:
    """Build user-facing copy for unavailable live Comfy metadata."""

    lines = ["Substitute could not load required live Comfy node definitions."]
    missing_classes = _missing_live_node_classes(error)
    missing_fields = _missing_live_node_fields(error)
    if missing_classes:
        lines.extend(("", "Missing definitions:"))
        lines.extend(f"- {class_type}" for class_type in missing_classes)
    if missing_fields:
        lines.extend(("", "Missing fields:"))
        lines.extend(f"- {field}" for field in missing_fields)
    lines.extend(
        (
            "",
            "Substitute cannot safely render or validate controls without live "
            "Comfy metadata.",
            "Start or restart ComfyUI and confirm the required custom nodes "
            "loaded successfully.",
        )
    )
    return "\n".join(lines)


def _live_node_definition_operation_context(
    error: LiveNodeDefinitionError,
    *,
    workflow_id: str | None,
    reason: str,
) -> SubstituteOperationContext:
    """Build structured operation context for live metadata failures."""

    cube_aliases = tuple(
        sorted(
            {
                cube_alias
                for item in error.missing_definitions
                for cube_alias in item.cube_aliases
                if cube_alias.strip()
            }
        )
    )
    node_names = tuple(
        sorted(
            {
                node_name
                for item in error.missing_definitions
                for node_name in item.node_names
                if node_name.strip()
            }
        )
    )
    return SubstituteOperationContext(
        operation=error.operation,
        workflow_id=workflow_id,
        values={
            "projection_reason": reason,
            "missing_node_classes": _missing_live_node_classes(error),
            "missing_fields": _missing_live_node_fields(error),
            "cube_aliases": cube_aliases,
            "node_names": node_names,
        },
    )


def _live_node_definition_report_fingerprint(
    error: LiveNodeDefinitionError,
    *,
    workflow_id: str | None,
    reason: str,
) -> LiveNodeDefinitionReportFingerprint:
    """Build a stable fingerprint for one live metadata report."""

    context = _live_node_definition_operation_context(
        error,
        workflow_id=workflow_id,
        reason=reason,
    )
    return LiveNodeDefinitionReportFingerprint(
        workflow_id=workflow_id or "",
        reason=reason,
        operation=error.operation,
        missing_node_classes=tuple(
            cast(tuple[str, ...], context.values["missing_node_classes"])
        ),
        missing_fields=tuple(cast(tuple[str, ...], context.values["missing_fields"])),
        cube_aliases=tuple(cast(tuple[str, ...], context.values["cube_aliases"])),
        node_names=tuple(cast(tuple[str, ...], context.values["node_names"])),
    )


def _has_unowned_live_node_definition_error(error: LiveNodeDefinitionError) -> bool:
    """Return whether any missing live metadata lacks cube attribution."""

    return any(not item.cube_aliases for item in error.missing_definitions) or bool(
        error.missing_fields
    )


def _issue_display_lines(issues: Sequence[CubeRuntimeIssue]) -> tuple[str, ...]:
    """Return concise display lines for cube runtime issues."""

    lines: list[str] = []
    for issue in issues:
        if issue.message:
            lines.append(issue.message)
        if issue.missing_node_classes:
            lines.extend(
                f"Missing definition: {class_type}"
                for class_type in issue.missing_node_classes[:4]
            )
        if issue.missing_fields:
            lines.extend(
                f"Missing field: {field}" for field in issue.missing_fields[:4]
            )
        if issue.recommended_action:
            lines.append(issue.recommended_action)
    return tuple(dict.fromkeys(lines))
