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

"""Test the atomic shell restoration.workspace-restoration flow."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from pytest import MonkeyPatch

from substitute.domain.workflow import WorkflowState
import substitute.domain.workspace_snapshot as snap
import substitute.presentation.shell.generation_result_workspace_materializer as generation_result_workspace_materializer_module
import substitute.presentation.shell.shell_layout_restore_controller as shell_layout_restore_controller_module
import substitute.presentation.shell.shell_prehydrated_restore_controller as shell_prehydrated_restore_controller_module
import substitute.presentation.shell.generation_action_controller as action_controller
from substitute.presentation.shell.generation_queue_controller import (
    GenerationQueueController,
)
from substitute.presentation.shell.generation_result_workspace_materializer import (
    GenerationResultWorkspaceMaterializer,
)
from substitute.presentation.shell.main_window import MainWindow
from substitute.presentation.shell.shell_layout_restore_controller import (
    ShellLayoutRestoreController,
)
from substitute.presentation.shell.shell_workspace_materialization_port import (
    ShellWorkspaceMaterializationPort,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)

import tests.presentation.shell.restoration.restoration_support as restoration


def test_hidden_restore_runtime_prep_hydrates_installs_without_projection_or_layout() -> (
    None
):
    """Keep hidden hydration independent from visible projection and layout."""

    view: Any = restoration.restore_view(restoration.workspace())
    events: list[str] = []
    hydrated = restoration.workspace(active_route="wf-a")

    def hydrate(
        _snapshot: snap.WorkspaceSnapshot, *, operation: str
    ) -> snap.WorkspaceSnapshot:
        """Record hidden hydration and return a hydrated snapshot."""

        events.append(f"hydrate:{operation}")
        return hydrated

    def install(snapshot: snap.WorkspaceSnapshot) -> None:
        """Record hidden hydrated snapshot installation."""

        events.append(f"install:{snapshot.active_route}")

    view.workspace_restore_controller = SimpleNamespace(
        hydrate_restored_workspace_snapshot=hydrate,
        install_hydrated_prehydrated_workspace=install,
    )
    view.restore_projection_controller = SimpleNamespace(
        project_restored_workflow=lambda workflow_id: events.append(
            f"project:{workflow_id}"
        ),
        project_restored_settings=lambda: events.append("settings"),
    )
    view.shell_layout_restore_controller = SimpleNamespace(
        apply_restored_shell_layout=lambda _snapshot: events.append("layout")
    )

    assert view.shell_prehydrated_restore_controller.prepare_initial_workspace_restore_runtime()
    assert events == [
        "hydrate:prepare_initial_workspace_restore_runtime",
        "install:wf-a",
    ]
    assert (
        view.shell_prehydrated_restore_controller.prehydrated_restore_runtime_prepared()
    )
    assert not view.shell_prehydrated_restore_controller.prehydrated_restore_finalized()
    assert view._prehydrated_active_workflow_projection_pending == "wf-a"


def test_prehydrated_input_mask_restore_defers_until_runtime_install() -> None:
    """Queue an input mask while prehydration lacks live workflow state."""

    view: Any = restoration.restore_view(restoration.workspace())
    reference = snap.InputMaskReference(
        mask_id=str(uuid4()),
        image_id=str(uuid4()),
        path=Path("mask.png"),
        association_key=("Cube", "load_mask"),
    )

    assert view.workspace_restore_image_adapter.restore_input_mask(reference)
    assert view._deferred_prehydrated_input_masks == [reference]


def test_hidden_restore_runtime_replays_deferred_masks_after_install() -> None:
    """Replay queued masks only after the hydrated workflow is installed."""

    image_id = UUID("11111111-1111-4111-8111-111111111111")
    snapshot_mask_id = UUID("22222222-2222-4222-8222-222222222222")
    live_mask_id = UUID("33333333-3333-4333-8333-333333333333")
    association_key = ("Cube", "load_mask")
    reference = snap.InputMaskReference(
        mask_id=str(snapshot_mask_id),
        image_id=str(image_id),
        path=Path("mask.png"),
        association_key=association_key,
    )
    hydrated = restoration.workspace_with_input_mask(
        image_id=image_id,
        mask_id=snapshot_mask_id,
        association_key=association_key,
        reference=reference,
    )
    view: Any = restoration.restore_view(hydrated)
    view._deferred_prehydrated_input_masks = [reference]
    events: list[str] = []
    restore_calls: list[dict[str, object]] = []

    def install(snapshot: snap.WorkspaceSnapshot) -> None:
        """Install real workflow state before mask replay."""

        events.append("install")
        view.workflow_session_service = SimpleNamespace(
            workflows={
                entry.workflow_id: entry.workflow for entry in snapshot.workflows
            }
        )

    def restore_input_mask(
        workflow_id: str, current_workflow: WorkflowState, **kwargs: object
    ) -> UUID:
        """Record mask replay after workflow installation."""

        events.append("restore_mask")
        restore_calls.append(
            {"workflow_id": workflow_id, "workflow": current_workflow, "kwargs": kwargs}
        )
        return live_mask_id

    def hydrate(
        _snapshot: snap.WorkspaceSnapshot, *, operation: str
    ) -> snap.WorkspaceSnapshot:
        """Return the prepared hydrated snapshot."""

        _ = operation
        return hydrated

    view.workspace_restore_controller = SimpleNamespace(
        hydrate_restored_workspace_snapshot=hydrate,
        install_hydrated_prehydrated_workspace=install,
    )
    view.input_canvas_state_service = SimpleNamespace(
        restore_input_mask=restore_input_mask
    )
    view.restored_ordered_mask_collections = SimpleNamespace(
        reconcile=lambda _workflows: events.append("reconcile_ordered_masks")
    )

    assert view.shell_prehydrated_restore_controller.prepare_initial_workspace_restore_runtime()
    workflow = hydrated.workflows[0].workflow
    assert events == ["install", "restore_mask", "reconcile_ordered_masks"]
    assert restore_calls == [
        {
            "workflow_id": "wf-a",
            "workflow": workflow,
            "kwargs": {
                "snapshot_mask_id": snapshot_mask_id,
                "image_id": image_id,
                "path": Path("mask.png"),
                "association_key": association_key,
            },
        }
    ]
    assert view._deferred_prehydrated_input_masks == []


def test_visible_restore_layout_finish_applies_layout_and_deferred_settings() -> None:
    """Apply projection, layout, and deferred settings in visible completion order."""

    view: Any = restoration.restore_view(
        restoration.workspace(active_route=SETTINGS_WORKSPACE_ROUTE)
    )
    events: list[str] = []
    view._prehydrated_restore_runtime_prepared = True
    view._prehydrated_active_workflow_projection_pending = "wf-a"
    view._prehydrated_settings_projection_pending = True
    view.restore_projection_controller = SimpleNamespace(
        project_restored_workflow=lambda workflow_id: events.append(
            f"project:{workflow_id}"
        ),
        project_restored_settings=lambda: events.append("settings"),
    )
    view.shell_layout_restore_controller = SimpleNamespace(
        apply_restored_shell_layout=lambda snapshot: events.append(
            f"layout:{snapshot is not None}"
        )
    )

    assert view.shell_prehydrated_restore_controller.finish_initial_workspace_restore_layout()
    assert events == ["project:wf-a", "layout:True", "settings"]
    assert view.shell_prehydrated_restore_controller.prehydrated_restore_finalized()
    assert view._prehydrated_active_workflow_projection_pending == ""
    assert not view._prehydrated_settings_projection_pending


def test_restore_split_methods_are_idempotent() -> None:
    """Avoid duplicating hidden and visible restoration on repeated requests."""

    view: Any = restoration.restore_view(restoration.workspace())
    events: list[str] = []

    def hydrate(
        snapshot: snap.WorkspaceSnapshot, *, operation: str
    ) -> snap.WorkspaceSnapshot:
        """Record hydration and return the same snapshot."""

        _ = operation
        events.append("hydrate")
        return snapshot

    view.workspace_restore_controller = SimpleNamespace(
        hydrate_restored_workspace_snapshot=hydrate,
        install_hydrated_prehydrated_workspace=lambda _snapshot: events.append(
            "install"
        ),
    )
    view.restore_projection_controller = SimpleNamespace(
        project_restored_workflow=lambda _workflow_id: events.append("project"),
        project_restored_settings=lambda: events.append("settings"),
    )
    view.shell_layout_restore_controller = SimpleNamespace(
        apply_restored_shell_layout=lambda _snapshot: events.append("layout")
    )

    assert view.shell_prehydrated_restore_controller.prepare_initial_workspace_restore_runtime()
    assert view.shell_prehydrated_restore_controller.prepare_initial_workspace_restore_runtime()
    assert view.shell_prehydrated_restore_controller.finish_initial_workspace_restore_layout()
    assert view.shell_prehydrated_restore_controller.finish_initial_workspace_restore_layout()
    assert events == ["hydrate", "install", "project", "layout"]


def test_finalize_initial_workspace_restore_delegates_to_split_flow() -> None:
    """Preserve the public full-restore entrypoint over the split lifecycle."""

    view: Any = restoration.restore_view(restoration.workspace())
    events: list[str] = []

    def hydrate(
        snapshot: snap.WorkspaceSnapshot, *, operation: str
    ) -> snap.WorkspaceSnapshot:
        """Record delegated hydration and return the same snapshot."""

        events.append(f"hydrate:{operation}")
        return snapshot

    view.workspace_restore_controller = SimpleNamespace(
        hydrate_restored_workspace_snapshot=hydrate,
        install_hydrated_prehydrated_workspace=lambda _snapshot: events.append(
            "install"
        ),
    )
    view.restore_projection_controller = SimpleNamespace(
        project_restored_workflow=lambda _workflow_id: events.append("project"),
        project_restored_settings=lambda: events.append("settings"),
    )
    view.shell_layout_restore_controller = SimpleNamespace(
        apply_restored_shell_layout=lambda _snapshot: events.append("layout")
    )

    view.shell_prehydrated_restore_controller.finalize_initial_workspace_restore()
    assert events == [
        "hydrate:prepare_initial_workspace_restore_runtime",
        "install",
        "project",
        "layout",
    ]


def test_pre_show_restore_projection_builds_editor_without_finalizing_layout(
    monkeypatch: MonkeyPatch,
) -> None:
    """Build live editor widgets while preserving pending visible finalization."""

    events: list[str] = []
    view = restoration.prepared_projection_view(monkeypatch, events)
    artifact = restoration.RestoreArtifact(
        active_workflow_id="wf-a", workflows=(object(),)
    )

    assert view.restore_projection_controller.start_pre_show_restore_projection(
        artifact, on_complete=lambda: events.append("complete")
    )
    assert view._active_workspace_route == "wf-a"
    assert events == [
        "activate:wf-a",
        "actions",
        "ensure:wf-a:True",
        "tab:wf-a:False",
        "cube_current:cube-stack",
        "editor_current:editor-panel",
        "refresh:True",
        "complete",
    ]
    assert not view.shell_prehydrated_restore_controller.prehydrated_restore_finalized()
    assert view._prehydrated_active_workflow_projection_pending == "wf-a"


def test_pre_show_restore_projection_skips_mismatched_cache_artifact() -> None:
    """Reject a cached projection whose active workflow identity differs."""

    view: Any = restoration.restore_view(restoration.workspace())
    events: list[str] = []
    view._prehydrated_restore_runtime_prepared = True
    view._prehydrated_active_workflow_projection_pending = "wf-a"
    artifact = restoration.RestoreArtifact(active_workflow_id="wf-other", workflows=())

    assert not view.restore_projection_controller.start_pre_show_restore_projection(
        artifact, on_complete=lambda: events.append("complete")
    )
    assert events == []


def test_pre_show_restore_projection_uses_live_workflow_without_cache_artifact(
    monkeypatch: MonkeyPatch,
) -> None:
    """Project the live workflow when cache artifacts are unavailable."""

    events: list[str] = []
    view = restoration.prepared_projection_view(monkeypatch, events)

    assert view.restore_projection_controller.start_pre_show_restore_projection(
        None, fallback_workflow_id="wf-a", on_complete=lambda: events.append("complete")
    )
    assert view._active_workspace_route == "wf-a"
    assert events == [
        "activate:wf-a",
        "actions",
        "ensure:wf-a:True",
        "tab:wf-a:False",
        "cube_current:cube-stack",
        "editor_current:editor-panel",
        "refresh:True",
        "complete",
    ]


def test_materialize_prehydrated_initial_workspace_uses_snapshot_without_hydration(
    monkeypatch: MonkeyPatch,
) -> None:
    """Materialize a saved restoration.workspace while backend startup remains pending."""

    snapshot = restoration.workspace()
    view: Any = restoration.restore_view(snapshot)
    events: list[str] = []

    class Materializer:
        """Record direct snapshot materialization."""

        def materialize(
            self, current_workspace: snap.WorkspaceSnapshot, port: object
        ) -> object:
            """Record the supplied restoration.workspace materialization request."""

            assert current_workspace is snapshot
            assert isinstance(port, ShellWorkspaceMaterializationPort)
            events.append("materialize")
            return SimpleNamespace(warnings=("restored output skipped",))

    monkeypatch.setattr(
        shell_prehydrated_restore_controller_module,
        "WorkspaceMaterializationService",
        Materializer,
    )

    assert view.shell_prehydrated_restore_controller.materialize_prehydrated_initial_workspace()
    assert events == ["materialize"]
    assert view._prehydrated_workspace_snapshot is snapshot
    assert view._prehydrated_restore_finalized
    assert view._initial_workspace_hydrated


def test_materialize_prehydrated_initial_workspace_prefers_supplied_restore_snapshot(
    monkeypatch: MonkeyPatch,
) -> None:
    """Use the supplied restore snapshot instead of placeholder prehydration state."""

    placeholder = restoration.workspace_without_cubes()
    restored = restoration.workspace()
    view: Any = restoration.restore_view(placeholder)
    materialized: list[snap.WorkspaceSnapshot] = []

    class Materializer:
        """Record direct snapshot materialization."""

        def materialize(
            self, current_workspace: snap.WorkspaceSnapshot, port: object
        ) -> object:
            """Record the supplied restoration.workspace materialization request."""

            assert isinstance(port, ShellWorkspaceMaterializationPort)
            materialized.append(current_workspace)
            return SimpleNamespace(warnings=())

    monkeypatch.setattr(
        shell_prehydrated_restore_controller_module,
        "WorkspaceMaterializationService",
        Materializer,
    )

    assert view.shell_prehydrated_restore_controller.materialize_prehydrated_initial_workspace(
        restored
    )
    assert materialized == [restored]
    assert view._prehydrated_workspace_snapshot is restored
    assert view._prehydrated_restore_finalized


def test_restored_queue_panel_visibility_refreshes_titlebar_segment(
    monkeypatch: MonkeyPatch,
) -> None:
    """Rederive the titlebar queue affordance after restoring panel visibility."""

    view: Any = MainWindow.__new__(MainWindow)
    snapshot = snap.ShellLayoutSnapshot(
        main_splitter_sizes=(1, 2), generation_queue_panel_visible=True
    )
    cluster = restoration.GenerationActionCluster()
    side_panel_host = restoration.SidePanelHost()
    view._pending_restored_shell_layout = snapshot
    view._backend_state = "ready"
    view._active_workspace_route = "wf-a"
    view.generationActionCluster = cluster
    view.sidePanelHost = side_panel_host
    view.workflow_session_service = SimpleNamespace(
        active_workflow_id="wf-a",
        workflows={"wf-a": SimpleNamespace(cubes={"Cube": object()})},
    )
    view.workspace_generation_controller = SimpleNamespace(is_continuous_active=False)
    view.generation_job_queue_service = restoration.GenerationJobQueueService()
    view.comfy_runtime_actions = SimpleNamespace(
        set_comfy_output_panel_visible=lambda _visible: None
    )
    view.splitter = SimpleNamespace(
        sizes=lambda: [1, 2], setSizes=lambda _sizes: None, width=lambda: 200
    )
    view.editor_output_splitter = SimpleNamespace(setSizes=lambda _sizes: None)
    view.cube_stack_container = SimpleNamespace(setFixedWidth=lambda _width: None)
    view.cube_stacks = {}
    view.cubeStackModeButton = SimpleNamespace(setToolTip=lambda _tooltip: None)
    view.restore_finalized = SimpleNamespace(emit=lambda: None)
    view._pending_restore_projection_cache_capture_workflow_id = ""
    view.workspace_layout_controller = SimpleNamespace(
        current_main_splitter_sizes=lambda: (1, 2),
        remember_workflow_splitter_sizes=lambda _sizes: None,
        apply_workflow_splitter_sizes=lambda _sizes: None,
        workflow_splitter_sizes_for_snapshot=lambda: (1, 2),
    )
    view.cube_stack_presentation_controller = SimpleNamespace(
        restore_preference=lambda _compact: None,
        preference=SimpleNamespace(value="expanded"),
    )
    view.generation_queue_controller = GenerationQueueController(view)
    view.shell_layout_restore_controller = ShellLayoutRestoreController(view)
    view.generation_action_controller = action_controller.GenerationActionController(
        view
    )
    monkeypatch.setattr(
        shell_layout_restore_controller_module,
        "build_shell_layout_restore_plan",
        lambda *_args, **_kwargs: SimpleNamespace(
            cube_stack_compact=False,
            cube_stack_width=None,
            main_splitter_sizes=(),
            editor_output_splitter_sizes=(),
            side_panel_visible=False,
            side_panel_width=None,
            used_legacy_splitter=False,
            clamped_fields=(),
        ),
    )

    view.generation_action_controller.apply_generation_action_availability()
    assert cluster.queue_segment_visible_calls == [True]
    assert not side_panel_host.is_queue_panel_visible()
    view.shell_layout_restore_controller.apply_deferred_restored_shell_layout(
        snapshot, finalize=False
    )
    assert side_panel_host.is_queue_panel_visible()
    assert cluster.queue_segment_visible_calls == [True, False]


def test_generation_result_workspace_append_hydrates_before_materialization(
    monkeypatch: MonkeyPatch,
) -> None:
    """Hydrate a queued result after unique IDs and before append materialization."""

    view: Any = MainWindow.__new__(MainWindow)
    raw_snapshot = restoration.workspace(active_route="job-raw")
    unique_snapshot = restoration.workspace(active_route="job-open")
    unique_snapshot = snap.WorkspaceSnapshot(
        schema_version=unique_snapshot.schema_version,
        workflows=unique_snapshot.workflows,
        tab_order=unique_snapshot.tab_order,
        active_route=unique_snapshot.active_route,
        active_workflow_id=unique_snapshot.active_workflow_id,
        shell_layout=None,
    )
    hydrated_snapshot = restoration.workspace(active_route="job-hydrated")
    hydrated_snapshot = snap.WorkspaceSnapshot(
        schema_version=hydrated_snapshot.schema_version,
        workflows=hydrated_snapshot.workflows,
        tab_order=hydrated_snapshot.tab_order,
        active_route=hydrated_snapshot.active_route,
        active_workflow_id=hydrated_snapshot.active_workflow_id,
        shell_layout=None,
    )
    events: list[str] = []

    def make_unique(
        snapshot: snap.WorkspaceSnapshot,
    ) -> snap.WorkspaceSnapshot:
        """Record workflow-id uniquing and return the opened-tab snapshot."""

        assert snapshot is raw_snapshot
        events.append("unique")
        return unique_snapshot

    def hydrate(
        snapshot: snap.WorkspaceSnapshot, *, operation: str
    ) -> snap.WorkspaceSnapshot:
        """Record queue result hydration and return the hydrated snapshot."""

        assert snapshot is unique_snapshot
        assert operation == "materialize_generation_result_workspace"
        assert snapshot.shell_layout is None
        events.append("hydrate")
        return hydrated_snapshot

    class Materializer:
        """Record the snapshot passed to append materialization."""

        def materialize_into_existing_workspace(
            self, snapshot: snap.WorkspaceSnapshot, port: object
        ) -> object:
            """Record append materialization and return deterministic warnings."""

            assert snapshot is hydrated_snapshot
            assert snapshot.shell_layout is None
            assert isinstance(port, ShellWorkspaceMaterializationPort)
            events.append("materialize")
            return SimpleNamespace(warnings=("restored output skipped",))

    view.restored_workflow_materializer = SimpleNamespace(
        snapshot_with_unique_open_ids=make_unique
    )
    view.workspace_restore_controller = SimpleNamespace(
        hydrate_restored_workspace_snapshot=hydrate
    )
    view.generation_result_workspace_materializer = (
        GenerationResultWorkspaceMaterializer(view)
    )
    monkeypatch.setattr(
        generation_result_workspace_materializer_module,
        "WorkspaceMaterializationService",
        Materializer,
    )
    warnings = view.generation_result_workspace_materializer.materialize_generation_result_workspace(
        raw_snapshot
    )
    assert events == ["unique", "hydrate", "materialize"]
    assert warnings == ("restored output skipped",)
