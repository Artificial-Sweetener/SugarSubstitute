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

"""Tests for applying versioned Cube Library updates to workflow state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from substitute.application.cube_library import (
    CubeLibraryUpdateReason,
    LoadedCubeUpdateAction,
    LoadedCubeUpdateCandidate,
    LoadedCubeUpdateSelection,
)
from substitute.application.cubes import LoadedCubeDefinition, LoadedCubeRuntime
from substitute.application.workflows import WorkflowIssueState
from substitute.domain.cube_library import CubeUpdatePolicy
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.presentation.shell.workspace_cube_update_actions import (
    WorkspaceCubeUpdateActions,
    WorkspaceCubeUpdateView,
)


class _CubeLoadService:
    """Build deterministic versioned cube runtime state."""

    def __init__(self) -> None:
        """Initialize service call tracking."""

        self.invalidated = False
        self.loaded_versions: list[tuple[str, str]] = []
        self.buffer_patch: object | None = None
        self.fail_version_load = False

    def invalidate_catalog_cache(self) -> None:
        """Record cache invalidation."""

        self.invalidated = True

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return a loaded cube definition selected by version."""

        _ = cube_load_trace_id
        self.loaded_versions.append((cube_id, version))
        if self.fail_version_load:
            raise RuntimeError("version unavailable")
        return LoadedCubeDefinition(
            cube_id=cube_id,
            version=version,
            display_name="Demo Cube",
            graph={
                "nodes": {"sampler": {"class_type": "KSampler", "inputs": {}}},
                "surface": [],
            },
            ui_payload={"catalog_revision": "rev-2"},
        )

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
        """Return rebuilt runtime while recording the preservation patch."""

        _ = runtime_state, cube_load_trace_id
        self.buffer_patch = buffer_patch
        loaded = loaded_cube_definition
        if loaded is None:
            raise RuntimeError("expected loaded definition")
        cube_state = CubeState(
            cube_id=cube_id,
            version=loaded.version,
            alias=alias_name,
            original_cube=loaded.graph,
            buffer={"nodes": {}, "user": "kept"},
            display_name=loaded.display_name,
            ui=loaded.ui_payload,
        )
        return LoadedCubeRuntime(
            cube_id=cube_id,
            version=loaded.version,
            display_name=loaded.display_name,
            cube_definition=loaded.graph,
            cube_buffer=cube_state.buffer,
            cube_state=cube_state,
            ui_payload=loaded.ui_payload,
        )


class _NodeBehaviorService:
    """Return a dummy runtime object."""

    def prepare_runtime_state(
        self,
        loaded_cube: LoadedCubeDefinition,
        alias_name: str,
    ) -> object:
        """Return a deterministic runtime marker."""

        return {"cube_id": loaded_cube.cube_id, "alias": alias_name}


@dataclass
class _WorkflowSessionService:
    """Expose active workflow lookup."""

    workflows: Mapping[str, WorkflowState]
    active_workflow_id: str = "workflow-1"

    def get_workflow(self, workflow_id: str) -> WorkflowState | None:
        """Return one workflow by id."""

        return self.workflows.get(workflow_id)


@dataclass
class _LoadedCubeSurfaceActions:
    """Capture surface refresh requests."""

    marked_stale: list[tuple[str, str, str]] = field(default_factory=list)
    refreshed: list[tuple[str, str]] = field(default_factory=list)

    def refresh_loaded_cube_surface_async(
        self,
        workflow_id: str,
        cube_alias: str,
        on_complete: object,
        *,
        wait_for_complete: bool = False,
    ) -> None:
        """Record refresh requests."""

        _ = on_complete, wait_for_complete
        self.refreshed.append((workflow_id, cube_alias))

    def mark_loaded_cube_surface_stale(
        self,
        workflow_id: str,
        cube_alias: str,
        *,
        reason: str,
    ) -> None:
        """Record stale markers."""

        self.marked_stale.append((workflow_id, cube_alias, reason))


@dataclass
class _View:
    """Bundle update action dependencies."""

    cube_load_service: _CubeLoadService
    node_behavior_service: _NodeBehaviorService
    workflow_session_service: _WorkflowSessionService
    workspace_loaded_cube_surface_actions: _LoadedCubeSurfaceActions
    workflow_issue_state: WorkflowIssueState

    def refresh_active_workflow_surface(self) -> None:
        """Satisfy the update view protocol."""


def test_apply_update_loads_target_version_and_replaces_cube() -> None:
    """Manual updates should load the selected version and replace workflow state."""

    workflow = _workflow()
    cube_loader = _CubeLoadService()
    controller = _LoadedCubeSurfaceActions()
    actions = _actions(workflow, cube_loader=cube_loader, controller=controller)
    candidate = _candidate()

    failures = actions.apply_update_selections(
        (
            LoadedCubeUpdateSelection(
                candidate=candidate,
                action=LoadedCubeUpdateAction.UPDATE_INSTANCE,
                target_version="2.0",
            ),
        )
    )

    assert failures == ()
    assert cube_loader.invalidated is True
    assert cube_loader.loaded_versions == [("owner/repo/demo.cube", "2.0")]
    assert workflow.cubes["Demo"].version == "2.0"
    assert workflow.cubes["Demo"].update_policy == CubeUpdatePolicy.PINNED
    assert controller.marked_stale == [
        ("workflow-1", "Demo", "cube_definition_updated")
    ]
    assert controller.refreshed == [("workflow-1", "Demo")]


def test_follow_latest_success_persists_policy() -> None:
    """Automatic follow-latest updates should preserve follow-latest policy."""

    workflow = _workflow()
    actions = _actions(workflow)

    failures = actions.apply_update_selections(
        (
            LoadedCubeUpdateSelection(
                candidate=_candidate(update_policy=CubeUpdatePolicy.FOLLOW_LATEST),
                action=LoadedCubeUpdateAction.FOLLOW_LATEST,
                target_version="2.0",
            ),
        )
    )

    assert failures == ()
    assert workflow.cubes["Demo"].update_policy == CubeUpdatePolicy.FOLLOW_LATEST


def test_update_matching_version_updates_all_same_version_instances() -> None:
    """Bulk update should target matching cube id and version, not exact refs."""

    workflow = _workflow()
    workflow.cubes["Copy"] = CubeState(
        cube_id="owner/repo/demo.cube",
        version="1.0",
        alias="Copy",
        original_cube={"nodes": {}},
        buffer={"nodes": {}},
    )
    workflow.stack_order.append("Copy")
    workflow.cubes["Other"] = CubeState(
        cube_id="owner/repo/demo.cube",
        version="1.1",
        alias="Other",
        original_cube={"nodes": {}},
        buffer={"nodes": {}},
    )
    workflow.stack_order.append("Other")
    cube_loader = _CubeLoadService()
    actions = _actions(workflow, cube_loader=cube_loader)

    failures = actions.apply_update_selections(
        (
            LoadedCubeUpdateSelection(
                candidate=_candidate(),
                action=LoadedCubeUpdateAction.UPDATE_MATCHING_VERSION,
                target_version="2.0",
            ),
        )
    )

    assert failures == ()
    assert workflow.cubes["Demo"].version == "2.0"
    assert workflow.cubes["Copy"].version == "2.0"
    assert workflow.cubes["Other"].version == "1.1"
    assert cube_loader.loaded_versions == [
        ("owner/repo/demo.cube", "2.0"),
        ("owner/repo/demo.cube", "2.0"),
    ]


def test_follow_latest_failure_pins_existing_cube_and_records_issue() -> None:
    """Failed automatic updates should leave the old cube and stop retry churn."""

    workflow = _workflow(update_policy=CubeUpdatePolicy.FOLLOW_LATEST)
    cube_loader = _CubeLoadService()
    cube_loader.fail_version_load = True
    issue_state = WorkflowIssueState()
    actions = _actions(
        workflow,
        cube_loader=cube_loader,
        workflow_issue_state=issue_state,
    )

    failures = actions.apply_update_selections(
        (
            LoadedCubeUpdateSelection(
                candidate=_candidate(update_policy=CubeUpdatePolicy.FOLLOW_LATEST),
                action=LoadedCubeUpdateAction.FOLLOW_LATEST,
                target_version="2.0",
            ),
        )
    )

    assert len(failures) == 1
    assert workflow.cubes["Demo"].version == "1.0"
    assert workflow.cubes["Demo"].update_policy == CubeUpdatePolicy.PINNED
    issues = issue_state.issues_for_cube("workflow-1", "Demo")
    assert len(issues) == 1
    assert "version unavailable" in issues[0].message


def _workflow(
    *,
    update_policy: CubeUpdatePolicy = CubeUpdatePolicy.PINNED,
) -> WorkflowState:
    """Build a workflow containing one loaded cube."""

    return WorkflowState(
        cubes={
            "Demo": CubeState(
                cube_id="owner/repo/demo.cube",
                version="1.0",
                alias="Demo",
                original_cube={"nodes": {"sampler": {"inputs": {"steps": 20}}}},
                buffer={"nodes": {"sampler": {"inputs": {"steps": 30}}}},
                update_policy=update_policy,
            )
        },
        stack_order=["Demo"],
    )


def _actions(
    workflow: WorkflowState,
    *,
    cube_loader: _CubeLoadService | None = None,
    controller: _LoadedCubeSurfaceActions | None = None,
    workflow_issue_state: WorkflowIssueState | None = None,
) -> WorkspaceCubeUpdateActions:
    """Build update actions around one workflow."""

    return WorkspaceCubeUpdateActions(
        cast(
            WorkspaceCubeUpdateView,
            _View(
                cube_load_service=cube_loader or _CubeLoadService(),
                node_behavior_service=_NodeBehaviorService(),
                workflow_session_service=_WorkflowSessionService(
                    workflows={"workflow-1": workflow}
                ),
                workspace_loaded_cube_surface_actions=(
                    controller or _LoadedCubeSurfaceActions()
                ),
                workflow_issue_state=workflow_issue_state or WorkflowIssueState(),
            ),
        ),
    )


def _candidate(
    *,
    update_policy: CubeUpdatePolicy = CubeUpdatePolicy.PINNED,
) -> LoadedCubeUpdateCandidate:
    """Build one update candidate."""

    return LoadedCubeUpdateCandidate(
        workflow_id="workflow-1",
        workflow_name="Workflow One",
        cube_alias="Demo",
        cube_id="owner/repo/demo.cube",
        current_version="1.0",
        latest_version="2.0",
        catalog_revision="rev-2",
        display_name="Demo Cube",
        reason=CubeLibraryUpdateReason.VERSION_DRIFT,
        update_policy=update_policy,
    )
