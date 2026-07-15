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

"""Tests for startup session restore planning."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone

from substitute.application.ports import SessionSnapshotRepository
from substitute.application.workspace_state import (
    APP_PROJECTION_VERSION,
    InitialWorkspaceRestorePlan,
    InitialWorkspaceRestorePlanService,
    RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
    RestoreProjectionArtifact,
    RestoreProjectionCacheRepository,
    RestoreProjectionCacheState,
    SnapshotNormalizationService,
    workspace_projection_fingerprint,
)
from substitute.domain.session import (
    SESSION_SNAPSHOT_SCHEMA_VERSION,
    SessionSnapshot,
)
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    ShellLayoutSnapshot,
    WindowGeometrySnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)


@dataclass
class _Repository:
    """Return one configured startup snapshot."""

    snapshot: SessionSnapshot | None

    def load(self) -> SessionSnapshot | None:
        """Return the configured snapshot."""

        return self.snapshot

    def save(self, snapshot: SessionSnapshot) -> None:
        """Accept protocol save calls not used by these tests."""

        self.snapshot = snapshot


class _FailingRepository:
    """Raise during startup plan loading."""

    def load(self) -> SessionSnapshot | None:
        """Raise a recoverable load failure."""

        raise RuntimeError("load failed")

    def save(self, _snapshot: SessionSnapshot) -> None:
        """Accept protocol save calls not used by these tests."""


def test_initial_restore_plan_returns_empty_when_no_session() -> None:
    """Missing sessions should preserve fallback startup behavior."""

    plan = _build_plan(_Repository(None))

    assert plan.workspace is None
    assert plan.shell_placement is None
    assert plan.warnings == ()


def test_initial_restore_plan_returns_normalized_workspace_and_shell_placement() -> (
    None
):
    """Valid sessions should provide one normalized workspace and placement."""

    geometry = WindowGeometrySnapshot(x=10, y=20, width=1200, height=800)
    session = _session(
        _workspace(
            shell_layout=ShellLayoutSnapshot(
                geometry=geometry,
                window_display_state="normal",
            )
        )
    )

    plan = _build_plan(_Repository(session))

    assert plan.workspace is not None
    assert plan.workspace.active_route == "wf-a"
    assert plan.shell_placement is not None
    assert plan.shell_placement.geometry == geometry
    assert plan.shell_placement.window_display_state == "normal"
    assert plan.shell_placement.maximized is False


def test_initial_restore_plan_keeps_workspace_when_layout_has_no_geometry() -> None:
    """Snapshots without geometry should still hydrate workflow state."""

    session = _session(
        _workspace(
            shell_layout=ShellLayoutSnapshot(
                geometry=None,
                window_display_state="normal",
                maximized=False,
            )
        )
    )

    plan = _build_plan(_Repository(session))

    assert plan.workspace is not None
    assert plan.shell_placement is None


def test_initial_restore_plan_uses_display_state_without_geometry() -> None:
    """Maximized or fullscreen sessions should restore display state pre-show."""

    session = _session(
        _workspace(
            shell_layout=ShellLayoutSnapshot(
                geometry=None,
                window_display_state="maximized",
                maximized=True,
            )
        )
    )

    plan = _build_plan(_Repository(session))

    assert plan.workspace is not None
    assert plan.shell_placement is not None
    assert plan.shell_placement.geometry is None
    assert plan.shell_placement.window_display_state == "maximized"
    assert plan.shell_placement.maximized is True


def test_initial_restore_plan_preserves_normalization_warnings() -> None:
    """Startup logs and tests should be able to see snapshot repairs."""

    workflow = _workflow("wf-a")
    session = _session(
        WorkspaceSnapshot(
            schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
            workflows=(workflow, workflow),
            tab_order=("missing", "wf-a", "wf-a"),
            active_route="wf-a",
            active_workflow_id="wf-a",
            shell_layout=None,
        )
    )

    plan = _build_plan(_Repository(session))

    assert plan.workspace is not None
    assert plan.workspace.tab_order == ("wf-a",)
    assert "Dropped duplicate workflow id wf-a." in plan.warnings
    assert "Removed stale workflow id missing from tab order." in plan.warnings


def test_initial_restore_plan_returns_empty_after_load_failure() -> None:
    """Recoverable repository failures should not block startup."""

    plan = _build_plan(_FailingRepository())

    assert plan.workspace is None
    assert plan.shell_placement is None
    assert plan.warnings == ()


def test_initial_restore_plan_reports_missing_projection_cache() -> None:
    """Missing projection cache should not affect normal workspace restore."""

    session = _session(_workspace(shell_layout=None))
    plan = _build_plan(
        _Repository(session),
        restore_projection_repository=_ProjectionRepository(None),
        restore_projection_target_key="target",
    )

    assert plan.provisional_restore_projection is None
    assert plan.restore_projection_validation is not None
    assert (
        plan.restore_projection_validation.state is RestoreProjectionCacheState.MISSING
    )


def test_initial_restore_plan_accepts_valid_provisional_projection_cache() -> None:
    """A locally matching cache should be held for later backend validation."""

    workspace = _workspace(shell_layout=None)
    artifact = _projection_artifact(workspace, target_key="target")

    plan = _build_plan(
        _Repository(_session(workspace)),
        restore_projection_repository=_ProjectionRepository(artifact),
        restore_projection_target_key="target",
    )

    assert plan.provisional_restore_projection == artifact
    assert plan.restore_projection_validation is not None
    assert (
        plan.restore_projection_validation.state
        is RestoreProjectionCacheState.BACKEND_PENDING
    )


def test_initial_restore_plan_rejects_target_mismatched_projection_cache() -> None:
    """A cache for another backend target must not become provisional work."""

    workspace = _workspace(shell_layout=None)
    artifact = _projection_artifact(workspace, target_key="other")

    plan = _build_plan(
        _Repository(_session(workspace)),
        restore_projection_repository=_ProjectionRepository(artifact),
        restore_projection_target_key="target",
    )

    assert plan.provisional_restore_projection is None
    assert plan.restore_projection_validation is not None
    assert (
        plan.restore_projection_validation.state
        is RestoreProjectionCacheState.TARGET_MISMATCH
    )


def test_initial_restore_plan_clears_invalid_projection_cache() -> None:
    """Startup should discard projection caches that cannot safely rebuild the UI."""

    workspace = _workspace(shell_layout=None)
    artifact = replace(
        _projection_artifact(workspace, target_key="target"),
        projection={
            "nodes": {
                "upscale_by_factor": {
                    "value": {
                        "label": "Scale Factor",
                        "min": -9_223_372_036_854_775_807,
                        "max": 9_223_372_036_854_775_807,
                        "step": 0.1,
                    }
                }
            }
        },
    )
    projection_repository = _ProjectionRepository(artifact)

    plan = _build_plan(
        _Repository(_session(workspace)),
        restore_projection_repository=projection_repository,
        restore_projection_target_key="target",
    )

    assert projection_repository.cleared is True
    assert projection_repository.artifact is None
    assert plan.provisional_restore_projection is None
    assert plan.restore_projection_validation is not None
    assert (
        plan.restore_projection_validation.state is RestoreProjectionCacheState.INVALID
    )


def _build_plan(
    repository: SessionSnapshotRepository,
    *,
    restore_projection_repository: RestoreProjectionCacheRepository | None = None,
    restore_projection_target_key: str = "",
) -> InitialWorkspaceRestorePlan:
    """Build a restore plan with production normalization."""

    return InitialWorkspaceRestorePlanService(
        repository=repository,
        normalizer=SnapshotNormalizationService(),
        restore_projection_repository=restore_projection_repository,
        restore_projection_target_key=restore_projection_target_key,
    ).build()


class _ProjectionRepository:
    """Return one configured restore projection cache artifact."""

    def __init__(self, artifact: RestoreProjectionArtifact | None) -> None:
        """Store the artifact returned by load."""

        self.artifact = artifact
        self.cleared = False

    def load(self) -> RestoreProjectionArtifact | None:
        """Return the configured cache artifact."""

        return self.artifact

    def save(self, artifact: RestoreProjectionArtifact) -> None:
        """Replace the configured cache artifact."""

        self.artifact = artifact

    def clear(self) -> None:
        """Clear the configured cache artifact."""

        self.artifact = None
        self.cleared = True


def _session(workspace: WorkspaceSnapshot) -> SessionSnapshot:
    """Build one deterministic session snapshot."""

    return SessionSnapshot(
        schema_version=SESSION_SNAPSHOT_SCHEMA_VERSION,
        captured_at=datetime(2026, 5, 8, 12, tzinfo=timezone.utc),
        workspace=workspace,
    )


def _workspace(
    *,
    shell_layout: ShellLayoutSnapshot | None,
) -> WorkspaceSnapshot:
    """Build one valid workspace snapshot."""

    return WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(_workflow("wf-a"),),
        tab_order=("wf-a",),
        active_route="wf-a",
        active_workflow_id="wf-a",
        shell_layout=shell_layout,
    )


def _workflow(workflow_id: str) -> WorkflowSnapshot:
    """Build one restorable workflow tab."""

    return WorkflowSnapshot(
        workflow_id=workflow_id,
        tab_label="Workflow",
        workflow=WorkflowState(),
    )


def _projection_artifact(
    workspace: WorkspaceSnapshot,
    *,
    target_key: str,
) -> RestoreProjectionArtifact:
    """Build one minimal restore projection artifact for planning tests."""

    return RestoreProjectionArtifact(
        schema_version=RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
        created_at="2026-05-10T00:00:00Z",
        app_projection_version=APP_PROJECTION_VERSION,
        target_key=target_key,
        workspace_fingerprint=workspace_projection_fingerprint(workspace),
        active_route=workspace.active_route,
        active_workflow_id=workspace.active_workflow_id,
        workflows=(),
        prompt_editor_feature_profile_fingerprint="prompt",
        node_definition_fingerprints={},
        cube_definition_fingerprints={},
        projection={},
    )
