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

"""Track recoverable runtime issues scoped to workflow cubes."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, app_text

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from substitute.application.cube_library.update_detection import (
    LoadedCubeUpdateCandidate,
)
from substitute.application.node_behavior.live_definition_authority import (
    LiveNodeDefinitionError,
)


class CubeRuntimeIssueSeverity(StrEnum):
    """Describe how strongly a runtime issue should affect workflow behavior."""

    WARNING = "warning"
    ERROR = "error"


class CubeRuntimeIssueKind(StrEnum):
    """Classify recoverable cube runtime failures."""

    MISSING_LIVE_NODE_DEFINITION = "missing_live_node_definition"
    MISSING_LIVE_NODE_FIELD = "missing_live_node_field"
    STALE_CUBE_DEFINITION = "stale_cube_definition"
    CUBE_LIBRARY_UPDATE_FAILED = "cube_library_update_failed"
    INVALID_CUBE_CONTRACT = "invalid_cube_contract"
    PROJECTION_HYDRATION_FAILED = "projection_hydration_failed"


class CubeRuntimeIssueSource(StrEnum):
    """Identify the subsystem that produced an issue."""

    PROJECTION = "projection"
    CUBE_LIBRARY = "cube_library"
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class CubeRuntimeIssue:
    """Describe one recoverable issue attached to a loaded workflow cube."""

    workflow_id: str
    cube_alias: str
    severity: CubeRuntimeIssueSeverity
    kind: CubeRuntimeIssueKind
    message: ApplicationText
    operation: str
    source: CubeRuntimeIssueSource
    missing_node_classes: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    node_names: tuple[str, ...] = ()
    recommended_action: ApplicationText = ""
    update_candidate: LoadedCubeUpdateCandidate | None = None


class WorkflowIssueState:
    """Store runtime issues by workflow and cube without depending on widgets."""

    def __init__(self) -> None:
        """Initialize an empty workflow issue registry."""

        self._issues: dict[
            tuple[str, str, CubeRuntimeIssueSource],
            dict[tuple[object, ...], CubeRuntimeIssue],
        ] = {}

    def issues_for_cube(
        self,
        workflow_id: str,
        cube_alias: str,
    ) -> tuple[CubeRuntimeIssue, ...]:
        """Return deterministic issues for one workflow cube."""

        return self._sorted_issues(
            issue
            for (
                stored_workflow_id,
                stored_alias,
                _source,
            ), issues in self._issues.items()
            if stored_workflow_id == workflow_id and stored_alias == cube_alias
            for issue in issues.values()
        )

    def issues_for_workflow(self, workflow_id: str) -> tuple[CubeRuntimeIssue, ...]:
        """Return deterministic issues for one workflow."""

        return self._sorted_issues(
            issue
            for (stored_workflow_id, _alias, _source), issues in self._issues.items()
            if stored_workflow_id == workflow_id
            for issue in issues.values()
        )

    def errored_aliases(self, workflow_id: str) -> tuple[str, ...]:
        """Return cube aliases with at least one error-severity issue."""

        return tuple(
            sorted(
                {
                    issue.cube_alias
                    for issue in self.issues_for_workflow(workflow_id)
                    if issue.severity == CubeRuntimeIssueSeverity.ERROR
                }
            )
        )

    def has_error(self, workflow_id: str, cube_alias: str) -> bool:
        """Return whether one cube has an error-severity issue."""

        return any(
            issue.severity == CubeRuntimeIssueSeverity.ERROR
            for issue in self.issues_for_cube(workflow_id, cube_alias)
        )

    def replace_projection_issues(
        self,
        workflow_id: str,
        issues: Sequence[CubeRuntimeIssue],
        source: CubeRuntimeIssueSource,
    ) -> None:
        """Replace issues from one source for the workflow."""

        for key in [
            key for key in self._issues if key[0] == workflow_id and key[2] == source
        ]:
            self._issues.pop(key, None)
        self.add_issues(issues)

    def add_issues(self, issues: Sequence[CubeRuntimeIssue]) -> None:
        """Add issues while collapsing duplicate issue identities."""

        for issue in issues:
            key = (issue.workflow_id, issue.cube_alias, issue.source)
            self._issues.setdefault(key, {})[_issue_identity(issue)] = issue

    def clear_cube_issues(self, workflow_id: str, cube_alias: str) -> None:
        """Remove all issues attached to one workflow cube."""

        for key in [
            key
            for key in self._issues
            if key[0] == workflow_id and key[1] == cube_alias
        ]:
            self._issues.pop(key, None)

    def clear_workflow_issues(self, workflow_id: str) -> None:
        """Remove all issues attached to one workflow."""

        for key in [key for key in self._issues if key[0] == workflow_id]:
            self._issues.pop(key, None)

    def clear_issues_by_kind(
        self,
        workflow_id: str,
        kind: CubeRuntimeIssueKind,
    ) -> None:
        """Remove issues of one kind from a workflow."""

        for key, issues in list(self._issues.items()):
            if key[0] != workflow_id:
                continue
            retained = {
                identity: issue
                for identity, issue in issues.items()
                if issue.kind != kind
            }
            if retained:
                self._issues[key] = retained
            else:
                self._issues.pop(key, None)

    @staticmethod
    def _sorted_issues(
        issues: Iterable[CubeRuntimeIssue],
    ) -> tuple[CubeRuntimeIssue, ...]:
        """Return issues in stable workflow, cube, source, kind order."""

        return tuple(
            sorted(
                issues,
                key=lambda issue: (
                    issue.workflow_id,
                    issue.cube_alias,
                    issue.source.value,
                    issue.kind.value,
                    issue.severity.value,
                    issue.operation,
                    issue.missing_node_classes,
                    issue.missing_fields,
                    issue.node_names,
                    issue.message,
                ),
            )
        )


def _issue_identity(issue: CubeRuntimeIssue) -> tuple[object, ...]:
    """Return a deterministic duplicate-collapse key for one issue."""

    return (
        issue.kind,
        issue.severity,
        issue.operation,
        issue.missing_node_classes,
        issue.missing_fields,
        issue.node_names,
        issue.message,
        issue.recommended_action,
    )


def live_node_definition_error_to_cube_issues(
    error: LiveNodeDefinitionError,
    *,
    workflow_id: str,
    source: CubeRuntimeIssueSource,
) -> tuple[CubeRuntimeIssue, ...]:
    """Convert a cube-attributed live metadata failure into runtime issues."""

    issues: list[CubeRuntimeIssue] = []
    for missing in error.missing_definitions:
        if not missing.cube_aliases:
            continue
        for cube_alias in missing.cube_aliases:
            issues.append(
                CubeRuntimeIssue(
                    workflow_id=workflow_id,
                    cube_alias=cube_alias,
                    severity=CubeRuntimeIssueSeverity.ERROR,
                    kind=CubeRuntimeIssueKind.MISSING_LIVE_NODE_DEFINITION,
                    message=(
                        app_text(
                            "This cube cannot be rendered because live Comfy metadata "
                            "is unavailable."
                        )
                    ),
                    operation=error.operation,
                    source=source,
                    missing_node_classes=(missing.class_type,),
                    node_names=missing.node_names,
                    recommended_action=(
                        "Update this cube from the Cube Library, or start or "
                        "restart ComfyUI and confirm required custom nodes loaded."
                    ),
                )
            )
    for missing_field in error.missing_fields:
        field_name = f"{missing_field.class_type}.{missing_field.field_key}"
        issues.append(
            CubeRuntimeIssue(
                workflow_id=workflow_id,
                cube_alias="",
                severity=CubeRuntimeIssueSeverity.ERROR,
                kind=CubeRuntimeIssueKind.MISSING_LIVE_NODE_FIELD,
                message=app_text(
                    "A required live Comfy field definition is unavailable."
                ),
                operation=error.operation,
                source=source,
                missing_fields=(field_name,),
                recommended_action=(
                    "Start or restart ComfyUI and confirm required custom nodes loaded."
                ),
            )
        )
    return tuple(issue for issue in issues if issue.cube_alias)


__all__ = [
    "CubeRuntimeIssue",
    "CubeRuntimeIssueKind",
    "CubeRuntimeIssueSeverity",
    "CubeRuntimeIssueSource",
    "WorkflowIssueState",
    "live_node_definition_error_to_cube_issues",
]
