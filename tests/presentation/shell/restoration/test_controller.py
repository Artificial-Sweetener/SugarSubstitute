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

"""Contract tests for shell workspace restore orchestration."""

from __future__ import annotations

from types import SimpleNamespace

from pytest import MonkeyPatch

from substitute.application.ports import CubeCatalogRecord, CubeCatalogSnapshot
from substitute.application.cube_library.update_detection import (
    LoadedCubeUpdateCandidate,
)
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from substitute.presentation.shell.workspace_restore_controller import (
    WorkspaceRestoreController,
    workspace_restore_controller_for,
)
from substitute.presentation.shell.shell_workspace_prehydration_port import (
    ShellWorkspacePrehydrationPort,
)
from substitute.presentation.shell.shell_workspace_materialization_port import (
    ShellWorkspaceMaterializationPort,
)
import substitute.presentation.shell.workspace_restore_controller as restore_module


def test_prehydrate_initial_workspace_uses_narrow_shell_port(
    monkeypatch: MonkeyPatch,
) -> None:
    """Prehydration should not expose the entire shell as the application port."""

    snapshot = _workspace()
    ports: list[object] = []
    shell = SimpleNamespace(_initial_workspace_hydrated=False)

    class _PrehydrationService:
        def prehydrate(
            self,
            workspace: WorkspaceSnapshot,
            port: object,
        ) -> object:
            """Record the workspace prehydration port."""

            assert workspace is snapshot
            ports.append(port)
            return SimpleNamespace(warnings=())

    monkeypatch.setattr(
        restore_module,
        "WorkspacePrehydrationService",
        _PrehydrationService,
    )

    assert WorkspaceRestoreController(shell).prehydrate_initial_workspace(snapshot)

    assert len(ports) == 1
    assert isinstance(ports[0], ShellWorkspacePrehydrationPort)


def test_hydrate_initial_workspace_uses_provided_snapshot_and_schedules_once(
    monkeypatch: MonkeyPatch,
) -> None:
    """A supplied startup snapshot should bypass session loading and blank creation."""

    snapshot = _workspace()
    calls: list[object] = []

    def restore_initial_workspace_snapshot(workspace: WorkspaceSnapshot) -> bool:
        """Record provided snapshot restoration."""

        calls.append(workspace)
        return True

    shell = SimpleNamespace(
        _initial_workspace_hydrated=False,
        _startup_timer=None,
        cube_library_update_controller=SimpleNamespace(
            schedule_startup_update_check=lambda: calls.append("schedule")
        ),
    )

    controller = WorkspaceRestoreController(shell)
    monkeypatch.setattr(
        controller,
        "restore_initial_workspace_snapshot",
        restore_initial_workspace_snapshot,
    )
    monkeypatch.setattr(
        controller,
        "restore_initial_workspace_from_session",
        lambda: (_ for _ in ()).throw(
            AssertionError("session repository should not be loaded")
        ),
    )
    controller.hydrate_initial_workspace(snapshot)
    controller.hydrate_initial_workspace(snapshot)

    assert calls == [snapshot, "schedule"]
    assert shell._initial_workspace_hydrated is True


def test_hydrate_initial_workspace_falls_back_to_blank_and_marks_running(
    monkeypatch: MonkeyPatch,
) -> None:
    """Blank startup should run when no restored session is available."""

    calls: list[str] = []
    shell = SimpleNamespace(
        _initial_workspace_hydrated=False,
        _startup_timer=None,
        _schedule_cube_library_startup_update_check=lambda: calls.append("schedule"),
        _shell_restore_lifecycle="constructing",
    )

    controller = WorkspaceRestoreController(shell)
    monkeypatch.setattr(
        controller,
        "restore_initial_workspace_from_session",
        lambda: False,
    )
    monkeypatch.setattr(
        restore_module,
        "initial_workspace_controller_for",
        lambda shell: SimpleNamespace(
            initialize_initial_workspace=lambda: calls.append("blank")
        ),
    )
    controller.hydrate_initial_workspace()
    controller.hydrate_initial_workspace()

    assert calls == ["blank", "schedule"]
    assert shell._shell_restore_lifecycle == "running"


def test_hydrate_initial_workspace_skips_blank_when_session_restores(
    monkeypatch: MonkeyPatch,
) -> None:
    """Restored sessions should not create the fallback blank workflow."""

    calls: list[str] = []
    shell = SimpleNamespace(
        _initial_workspace_hydrated=False,
        _startup_timer=None,
        cube_library_update_controller=SimpleNamespace(
            schedule_startup_update_check=lambda: calls.append("schedule")
        ),
    )

    controller = WorkspaceRestoreController(shell)
    monkeypatch.setattr(
        controller,
        "restore_initial_workspace_from_session",
        lambda: True,
    )
    monkeypatch.setattr(
        restore_module,
        "initial_workspace_controller_for",
        lambda shell: SimpleNamespace(
            initialize_initial_workspace=lambda: calls.append("blank")
        ),
    )

    controller.hydrate_initial_workspace()
    controller.hydrate_initial_workspace()

    assert calls == ["schedule"]
    assert shell._initial_workspace_hydrated is True


def test_restore_initial_workspace_snapshot_hydrates_materializes_and_marks_running(
    monkeypatch: MonkeyPatch,
) -> None:
    """Restoring a snapshot should hydrate, materialize, and leave lifecycle running."""

    snapshot = _workspace(active_workflow_id="wf-a")
    hydrated = _workspace(active_workflow_id="wf-a")
    events: list[str] = []

    class _Materializer:
        def materialize(
            self,
            workspace: WorkspaceSnapshot,
            port: object,
        ) -> object:
            """Record the materialized hydrated snapshot."""

            assert workspace is hydrated
            assert isinstance(port, ShellWorkspaceMaterializationPort)
            events.append("materialize")
            return SimpleNamespace(warnings=())

    def hydrate(
        workspace: WorkspaceSnapshot,
        *,
        operation: str,
    ) -> WorkspaceSnapshot:
        """Record restore hydration."""

        assert workspace is snapshot
        assert operation == "restore_initial_workspace_snapshot"
        events.append("hydrate")
        return hydrated

    shell = SimpleNamespace(
        _shell_restore_lifecycle="constructing",
        _pending_restored_shell_layout=None,
        _startup_timer=None,
        _pending_restore_projection_cache_capture_workflow_id="wf-a",
    )
    controller = WorkspaceRestoreController(shell)
    monkeypatch.setattr(controller, "hydrate_restored_workspace_snapshot", hydrate)
    monkeypatch.setattr(
        restore_module, "WorkspaceMaterializationService", _Materializer
    )

    result = controller.restore_initial_workspace_snapshot(snapshot)

    assert result is True
    assert events == ["hydrate", "materialize"]
    assert shell._shell_restore_lifecycle == "running"
    assert shell._pending_restore_projection_cache_capture_workflow_id == ""


def test_restore_update_preserve_keys_does_not_fetch_catalog_when_cache_missing() -> (
    None
):
    """Restore update detection should not block hydration on a fresh catalog call."""

    client = SimpleNamespace(
        get_catalog=lambda: (_ for _ in ()).throw(
            AssertionError("restore must not call backend get_catalog")
        )
    )
    shell = SimpleNamespace(
        cube_library_client=client,
        cube_load_service=SimpleNamespace(
            picker_catalog_snapshot=lambda: CubeCatalogSnapshot(
                entries=[],
                state="missing",
            )
        ),
    )

    preserve_keys = WorkspaceRestoreController(shell).restore_update_preserve_keys(
        _workspace_with_cube(version="1.0")
    )

    assert preserve_keys == frozenset()


def test_restore_update_preserve_keys_uses_cached_catalog_before_visible() -> None:
    """Cached catalog rows should queue stale restored cubes without refreshing."""

    queued: list[LoadedCubeUpdateCandidate] = []
    shell = SimpleNamespace(
        cube_library_client=SimpleNamespace(
            get_catalog=lambda: (_ for _ in ()).throw(
                AssertionError("restore must not call backend get_catalog")
            )
        ),
        cube_load_service=SimpleNamespace(
            picker_catalog_snapshot=lambda: CubeCatalogSnapshot(
                entries=[
                    CubeCatalogRecord(
                        cube_id="owner/repo/demo.cube",
                        version="2.0",
                        display_name="Demo Cube",
                    )
                ],
                state="fresh",
                catalog_revision="catalog-rev",
            )
        ),
        cube_library_update_controller=SimpleNamespace(
            queue_pending=lambda candidates: queued.extend(candidates)
        ),
        isVisible=lambda: False,
    )

    preserve_keys = WorkspaceRestoreController(shell).restore_update_preserve_keys(
        _workspace_with_cube(version="1.0")
    )

    assert preserve_keys == frozenset({("wf-a", "Demo")})
    assert len(queued) == 1
    assert queued[0].cube_id == "owner/repo/demo.cube"


def test_install_hydrated_prehydrated_workspace_replaces_session_state() -> None:
    """Hidden restore install should replace placeholder workflows with hydrated ones."""

    snapshot = _workspace(active_workflow_id="wf-b")
    replacements: list[dict[str, object]] = []

    def replace_workflows(
        workflows_by_id: dict[str, WorkflowState],
        *,
        active_workflow_id: str,
    ) -> None:
        """Record replacement of workflow session state."""

        replacements.append(
            {
                "workflow_ids": tuple(workflows_by_id),
                "active_workflow_id": active_workflow_id,
            }
        )

    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(replace_workflows=replace_workflows),
    )

    WorkspaceRestoreController(shell).install_hydrated_prehydrated_workspace(snapshot)

    assert replacements == [
        {"workflow_ids": ("wf-a", "wf-b"), "active_workflow_id": "wf-b"}
    ]
    assert tuple(shell._pending_restored_workflow_snapshots) == ("wf-a", "wf-b")
    assert shell._restored_workflow_snapshots_by_id == (
        shell._pending_restored_workflow_snapshots
    )
    assert shell._prehydrated_workspace_snapshot is snapshot


def test_active_workflow_id_from_snapshot_falls_back_to_active_route() -> None:
    """Active workflow resolution should prefer normalized ids, then active route."""

    snapshot = _workspace(active_workflow_id="missing", active_route="wf-b")

    assert WorkspaceRestoreController.active_workflow_id_from_snapshot(snapshot) == (
        "wf-b"
    )


def test_controller_factory_reuses_existing_shell_controller() -> None:
    """Shell composition should share one restore controller instance."""

    shell = SimpleNamespace()

    first = workspace_restore_controller_for(shell)
    second = workspace_restore_controller_for(shell)

    assert first is second
    assert shell.workspace_restore_controller is first


def _workspace(
    *,
    active_workflow_id: str = "wf-a",
    active_route: str = "wf-a",
) -> WorkspaceSnapshot:
    """Build a two-workflow restore snapshot."""

    return WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            _workflow_snapshot("wf-a"),
            _workflow_snapshot("wf-b"),
        ),
        tab_order=("wf-a", "wf-b"),
        active_route=active_route,
        active_workflow_id=active_workflow_id,
    )


def _workflow_snapshot(workflow_id: str) -> WorkflowSnapshot:
    """Build one minimal workflow snapshot."""

    return WorkflowSnapshot(
        workflow_id=workflow_id,
        tab_label=workflow_id,
        workflow=WorkflowState(),
    )


def _workspace_with_cube(*, version: str) -> WorkspaceSnapshot:
    """Build one restore snapshot containing a loaded Cube Library cube."""

    return WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="wf-a",
                tab_label="Workflow A",
                workflow=WorkflowState(
                    cubes={
                        "Demo": CubeState(
                            cube_id="owner/repo/demo.cube",
                            version=version,
                            alias="Demo",
                            original_cube={},
                            buffer={},
                            display_name="Demo Cube",
                        )
                    },
                    stack_order=["Demo"],
                ),
            ),
        ),
        tab_order=("wf-a",),
        active_route="wf-a",
        active_workflow_id="wf-a",
    )
