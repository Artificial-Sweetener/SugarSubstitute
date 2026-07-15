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

"""Apply selected Cube Library updates to loaded workflow cubes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, Protocol, cast

from substitute.application.cube_library import (
    CubeUpdatePolicy,
    LoadedCubeUpdateAction,
    LoadedCubeUpdateCandidate,
    LoadedCubeUpdateSelection,
)
from substitute.application.cubes import (
    CubeInstanceStateTransferService,
    LoadedCubeDefinition,
    LoadedCubeRuntime,
)
from substitute.application.node_behavior import NodeBehaviorRuntimeState
from substitute.application.workflows import WorkflowIssueState
from substitute.application.workflows.cube_runtime_issues import (
    CubeRuntimeIssue,
    CubeRuntimeIssueKind,
    CubeRuntimeIssueSeverity,
    CubeRuntimeIssueSource,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    CUBE_STRUCTURE_SURFACES,
    WorkflowInvalidationReason,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
    log_info,
)

_LOGGER = get_logger("presentation.shell.workspace_cube_update_actions")


def _mark_cube_update_surfaces_dirty(view: object, workflow_id: str) -> None:
    """Record cube-update maintenance intent when the shell exposes tracking."""

    service = getattr(view, "workflow_surface_invalidation_service", None)
    mark_dirty = getattr(service, "mark_dirty", None)
    if callable(mark_dirty):
        mark_dirty(
            workflow_id,
            CUBE_STRUCTURE_SURFACES,
            WorkflowInvalidationReason.NODE_DEFINITIONS_REFRESHED,
        )


class CubeLoadServiceProtocol(Protocol):
    """Describe cube-load operations needed for applying update selections."""

    def invalidate_catalog_cache(self) -> None:
        """Invalidate catalog and loaded-definition caches."""

    def load_cube_definition(
        self,
        cube_id: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return the latest loaded cube definition for a cube id."""

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return the loaded cube definition selected by version."""

    def build_loaded_cube_runtime(
        self,
        cube_id: str,
        alias_name: str,
        *,
        buffer_patch: object | None,
        runtime_state: object | None,
        loaded_cube_definition: LoadedCubeDefinition | None = None,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeRuntime:
        """Return a rebuilt loaded cube runtime."""


class NodeBehaviorServiceProtocol(Protocol):
    """Describe node behavior preparation needed for loaded cube updates."""

    def prepare_runtime_state(
        self,
        loaded_cube: LoadedCubeDefinition,
        alias_name: str,
    ) -> NodeBehaviorRuntimeState:
        """Return runtime node-behavior state for one loaded cube."""


class WorkflowStateProtocol(Protocol):
    """Describe mutable workflow state needed by update application."""

    cubes: dict[str, Any]
    stack_order: list[str]


class WorkflowSessionServiceProtocol(Protocol):
    """Describe workflow lookup behavior needed by update application."""

    active_workflow_id: str
    workflows: Mapping[str, WorkflowStateProtocol]

    def get_workflow(self, workflow_id: str) -> WorkflowStateProtocol | None:
        """Return workflow state for one workflow id."""


class LoadedCubeSurfaceActionsProtocol(Protocol):
    """Describe surface refresh behavior used after updating a loaded cube."""

    def refresh_loaded_cube_surface_async(
        self,
        workflow_id: str,
        cube_alias: str,
        on_complete: object,
        *,
        wait_for_complete: bool = False,
    ) -> None:
        """Refresh one loaded cube surface when its workflow is active."""

    def mark_loaded_cube_surface_stale(
        self,
        workflow_id: str,
        cube_alias: str,
        *,
        reason: str,
    ) -> None:
        """Mark one active editor cube surface stale before a refresh."""


class WorkspaceCubeUpdateView(Protocol):
    """Describe the shell dependencies used by loaded cube update actions."""

    cube_load_service: CubeLoadServiceProtocol
    node_behavior_service: NodeBehaviorServiceProtocol
    workflow_session_service: WorkflowSessionServiceProtocol
    workspace_loaded_cube_surface_actions: LoadedCubeSurfaceActionsProtocol
    workflow_issue_state: WorkflowIssueState


class WorkspaceCubeUpdateActions:
    """Apply accepted Cube Library update candidates to workflow state."""

    def __init__(self, view: WorkspaceCubeUpdateView) -> None:
        """Store shell dependencies for update application."""

        self._view = view
        self._state_transfer = CubeInstanceStateTransferService()

    def apply_selected_updates(
        self,
        candidates: Sequence[LoadedCubeUpdateCandidate],
    ) -> tuple[LoadedCubeUpdateCandidate, ...]:
        """Update selected loaded cubes and return candidates that failed."""

        failures = self.apply_update_selections(
            tuple(
                LoadedCubeUpdateSelection(
                    candidate=candidate,
                    action=LoadedCubeUpdateAction.UPDATE_INSTANCE,
                    target_version=candidate.latest_version,
                )
                for candidate in candidates
            )
        )
        return tuple(failure.candidate for failure in failures)

    def apply_update_selections(
        self,
        selections: Sequence[LoadedCubeUpdateSelection],
    ) -> tuple[LoadedCubeUpdateSelection, ...]:
        """Apply selected update actions and return selections that failed."""

        if not selections:
            return ()
        log_info(
            _LOGGER,
            "Starting selected Cube Library update batch",
            event="frontend_update_apply_batch_start",
            selection_count=len(selections),
            selected_aliases=[
                selection.candidate.cube_alias for selection in selections
            ],
            selected_actions=[selection.action.value for selection in selections],
        )
        self._view.cube_load_service.invalidate_catalog_cache()
        failures: list[LoadedCubeUpdateSelection] = []
        refreshed_active_aliases: list[tuple[str, str]] = []
        for selection in selections:
            try:
                refreshed_active_aliases.extend(self._apply_selection(selection))
            except Exception as error:
                failures.append(selection)
                candidate = selection.candidate
                if selection.action == LoadedCubeUpdateAction.FOLLOW_LATEST:
                    self._set_existing_policy(candidate, CubeUpdatePolicy.PINNED)
                self._record_update_failure_issue(selection, error)
                log_exception(
                    _LOGGER,
                    "Failed to update loaded Cube Library cube",
                    workflow_id=candidate.workflow_id,
                    cube_alias=candidate.cube_alias,
                    cube_id=candidate.cube_id,
                    current_version=candidate.current_version,
                    latest_version=candidate.latest_version,
                    action=selection.action.value,
                    error=repr(error),
                )
        self._refresh_surfaces(refreshed_active_aliases)
        log_info(
            _LOGGER,
            "Finished selected Cube Library update batch",
            event="frontend_update_apply_batch_finish",
            selection_count=len(selections),
            failure_count=len(failures),
            refreshed_active_aliases=list(refreshed_active_aliases),
        )
        return tuple(failures)

    def _record_update_failure_issue(
        self,
        selection: LoadedCubeUpdateSelection,
        error: Exception,
    ) -> None:
        """Record an actionable cube-library update issue for failed selections."""

        issue_state = getattr(self._view, "workflow_issue_state", None)
        add_issues = getattr(issue_state, "add_issues", None)
        if not callable(add_issues):
            return
        candidate = selection.candidate
        add_issues(
            (
                CubeRuntimeIssue(
                    workflow_id=candidate.workflow_id,
                    cube_alias=candidate.cube_alias,
                    severity=CubeRuntimeIssueSeverity.WARNING,
                    kind=CubeRuntimeIssueKind.CUBE_LIBRARY_UPDATE_FAILED,
                    message=(
                        "Substitute could not update this cube from the Cube Library: "
                        f"{error}"
                    ),
                    operation="cube_library_update",
                    source=CubeRuntimeIssueSource.CUBE_LIBRARY,
                    recommended_action=(
                        "Review the Cube Library update and try applying it again."
                    ),
                    update_candidate=candidate,
                ),
            )
        )

    def _apply_selection(
        self,
        selection: LoadedCubeUpdateSelection,
    ) -> tuple[tuple[str, str], ...]:
        """Apply one user-selected action and return active aliases to refresh."""

        if selection.action == LoadedCubeUpdateAction.KEEP_PINNED:
            self._set_existing_policy(selection.candidate, CubeUpdatePolicy.PINNED)
            log_info(
                _LOGGER,
                "Kept loaded Cube Library cube pinned",
                workflow_id=selection.candidate.workflow_id,
                cube_alias=selection.candidate.cube_alias,
                cube_id=selection.candidate.cube_id,
            )
            return ()
        if selection.action == LoadedCubeUpdateAction.UPDATE_MATCHING_VERSION:
            return tuple(
                refreshed
                for candidate in self._matching_version_candidates(selection.candidate)
                if (refreshed := self._apply_one(candidate, selection)) is not None
            )
        refreshed = self._apply_one(selection.candidate, selection)
        return () if refreshed is None else (refreshed,)

    def _apply_one(
        self,
        candidate: LoadedCubeUpdateCandidate,
        selection: LoadedCubeUpdateSelection,
    ) -> tuple[str, str] | None:
        """Apply one selected candidate and return active UI alias to refresh."""

        workflow = self._view.workflow_session_service.get_workflow(
            candidate.workflow_id
        )
        if workflow is None:
            log_info(
                _LOGGER,
                "Skipped Cube Library update because workflow was gone",
                workflow_id=candidate.workflow_id,
                cube_alias=candidate.cube_alias,
                cube_id=candidate.cube_id,
            )
            return None
        restored_cube = workflow.cubes.get(candidate.cube_alias)
        if restored_cube is None:
            log_info(
                _LOGGER,
                "Skipped Cube Library update because cube alias was gone",
                workflow_id=candidate.workflow_id,
                cube_alias=candidate.cube_alias,
                cube_id=candidate.cube_id,
            )
            return None
        trace_id = f"cube-update:{candidate.workflow_id}:{candidate.cube_alias}"
        log_info(
            _LOGGER,
            "Applying selected Cube Library update",
            event="frontend_update_apply_one_start",
            trace_id=trace_id,
            workflow_id=candidate.workflow_id,
            cube_alias=candidate.cube_alias,
            cube_id=candidate.cube_id,
            current_version=candidate.current_version,
            latest_version=candidate.latest_version,
            catalog_revision=candidate.catalog_revision,
            restored_cube_object_id=id(restored_cube),
            restored_buffer_object_id=id(getattr(restored_cube, "buffer", None)),
            restored_ui_keys=(
                sorted(getattr(restored_cube, "ui", {}))
                if isinstance(getattr(restored_cube, "ui", None), dict)
                else []
            ),
        )
        target_version = self._target_version(selection)
        if not target_version:
            raise ValueError(
                "Cube update selection is missing a target version "
                f"for alias '{candidate.cube_alias}' and cube '{candidate.cube_id}'."
            )
        loaded_cube = self._view.cube_load_service.load_cube_definition_version(
            candidate.cube_id,
            target_version,
            cube_load_trace_id=trace_id,
        )
        log_info(
            _LOGGER,
            "Loaded versioned Cube Library update definition",
            event="frontend_update_definition_loaded",
            trace_id=trace_id,
            workflow_id=candidate.workflow_id,
            cube_alias=candidate.cube_alias,
            requested_cube_id=candidate.cube_id,
            loaded_cube_id=loaded_cube.cube_id,
            loaded_version=loaded_cube.version,
            loaded_ui_keys=sorted(loaded_cube.ui_payload or {}),
        )
        runtime_state = self._view.node_behavior_service.prepare_runtime_state(
            loaded_cube,
            candidate.cube_alias,
        )
        transfer = self._state_transfer.transfer(
            old_cube=cast(Any, restored_cube),
            new_cube_definition=loaded_cube.graph,
        )
        log_info(
            _LOGGER,
            "Transferred cube instance state for update",
            workflow_id=candidate.workflow_id,
            cube_alias=candidate.cube_alias,
            cube_id=candidate.cube_id,
            preserved_surface_value_count=(
                transfer.report.preserved_surface_value_count
            ),
            dropped_surface_value_count=transfer.report.dropped_surface_value_count,
            preserved_node_input_count=transfer.report.preserved_node_input_count,
            dropped_node_input_count=transfer.report.dropped_node_input_count,
            preserved_link_count=transfer.report.preserved_link_count,
            dropped_link_count=transfer.report.dropped_link_count,
            added_control_ids=transfer.report.added_control_ids,
            removed_control_ids=transfer.report.removed_control_ids,
            incompatible_control_ids=transfer.report.incompatible_control_ids,
        )
        loaded_runtime = self._view.cube_load_service.build_loaded_cube_runtime(
            candidate.cube_id,
            candidate.cube_alias,
            buffer_patch=transfer.buffer_patch,
            runtime_state=runtime_state,
            loaded_cube_definition=loaded_cube,
            cube_load_trace_id=trace_id,
        )
        loaded_runtime.cube_state.update_policy = self._target_update_policy(selection)
        mark_stale = getattr(
            self._view.workspace_loaded_cube_surface_actions,
            "mark_loaded_cube_surface_stale",
            None,
        )
        if callable(mark_stale):
            mark_stale(
                candidate.workflow_id,
                candidate.cube_alias,
                reason="cube_definition_updated",
            )
        workflow.cubes[candidate.cube_alias] = loaded_runtime.cube_state
        _mark_cube_update_surfaces_dirty(self._view, candidate.workflow_id)
        log_info(
            _LOGGER,
            "Replaced workflow cube state after update",
            event="frontend_update_cube_state_replaced",
            trace_id=trace_id,
            workflow_id=candidate.workflow_id,
            cube_alias=candidate.cube_alias,
            old_cube_object_id=id(restored_cube),
            new_cube_object_id=id(loaded_runtime.cube_state),
            new_buffer_object_id=id(loaded_runtime.cube_buffer),
            loaded_cube_id=loaded_runtime.cube_id,
            loaded_version=loaded_runtime.version,
        )
        issue_state = getattr(self._view, "workflow_issue_state", None)
        clear_cube_issues = getattr(issue_state, "clear_cube_issues", None)
        if callable(clear_cube_issues):
            clear_cube_issues(candidate.workflow_id, candidate.cube_alias)
        log_info(
            _LOGGER,
            "Updated loaded Cube Library cube",
            workflow_id=candidate.workflow_id,
            cube_alias=candidate.cube_alias,
            cube_id=candidate.cube_id,
            current_version=candidate.current_version,
            latest_version=candidate.latest_version,
            action=selection.action.value,
            update_policy=loaded_runtime.cube_state.update_policy.value,
        )
        if (
            candidate.workflow_id
            != self._view.workflow_session_service.active_workflow_id
        ):
            return None
        return (candidate.workflow_id, candidate.cube_alias)

    def _matching_version_candidates(
        self,
        candidate: LoadedCubeUpdateCandidate,
    ) -> tuple[LoadedCubeUpdateCandidate, ...]:
        """Return workflow cube instances that share the current cube version."""

        matches: list[LoadedCubeUpdateCandidate] = []
        for (
            workflow_id,
            workflow,
        ) in self._view.workflow_session_service.workflows.items():
            for cube_alias, cube_state in workflow.cubes.items():
                if str(getattr(cube_state, "cube_id", "")) != candidate.cube_id:
                    continue
                if str(getattr(cube_state, "version", "")) != candidate.current_version:
                    continue
                matches.append(
                    replace(
                        candidate,
                        workflow_id=workflow_id,
                        workflow_name=workflow_id,
                        cube_alias=str(cube_alias),
                        current_version=str(getattr(cube_state, "version", "")),
                        update_policy=_loaded_update_policy(cube_state),
                    )
                )
        return tuple(matches)

    def _set_existing_policy(
        self,
        candidate: LoadedCubeUpdateCandidate,
        policy: CubeUpdatePolicy,
    ) -> None:
        """Persist a policy choice on an existing workflow cube instance."""

        workflow = self._view.workflow_session_service.get_workflow(
            candidate.workflow_id
        )
        if workflow is None:
            return
        cube_state = workflow.cubes.get(candidate.cube_alias)
        if cube_state is None:
            return
        setattr(cube_state, "update_policy", policy)

    def _target_version(
        self,
        selection: LoadedCubeUpdateSelection,
    ) -> str | None:
        """Return the target version selected by one user action."""

        if selection.action == LoadedCubeUpdateAction.SWITCH_TO_VERSION:
            return selection.target_version
        if selection.action == LoadedCubeUpdateAction.FOLLOW_LATEST:
            return selection.candidate.latest_version
        if selection.action == LoadedCubeUpdateAction.UPDATE_MATCHING_VERSION:
            return selection.candidate.latest_version
        if selection.action == LoadedCubeUpdateAction.UPDATE_INSTANCE:
            return selection.candidate.latest_version
        return None

    def _target_update_policy(
        self,
        selection: LoadedCubeUpdateSelection,
    ) -> CubeUpdatePolicy:
        """Return the persisted policy after applying one selected action."""

        if selection.action == LoadedCubeUpdateAction.FOLLOW_LATEST:
            return CubeUpdatePolicy.FOLLOW_LATEST
        return CubeUpdatePolicy.PINNED

    def _refresh_surfaces(self, aliases: Sequence[tuple[str, str]]) -> None:
        """Refresh active workflow surfaces affected by successful updates."""

        for workflow_id, cube_alias in aliases:
            log_debug(
                _LOGGER,
                "Refreshing updated Cube Library cube surface",
                event="frontend_update_refresh_requested",
                trace_id=f"cube-update:{workflow_id}:{cube_alias}",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
            )
            self._view.workspace_loaded_cube_surface_actions.refresh_loaded_cube_surface_async(
                workflow_id,
                cube_alias,
                lambda _refreshed: None,
            )


__all__ = ["WorkspaceCubeUpdateActions", "WorkspaceCubeUpdateView"]


def _loaded_update_policy(cube_state: object) -> CubeUpdatePolicy:
    """Return the update policy stored on one workflow cube state."""

    update_policy = getattr(cube_state, "update_policy", None)
    if isinstance(update_policy, CubeUpdatePolicy):
        return update_policy
    return CubeUpdatePolicy.PINNED
