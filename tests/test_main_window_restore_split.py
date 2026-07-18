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

"""Tests for split prehydrated workspace restore finalization."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from pytest import MonkeyPatch

from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import (
    InputMaskReference,
    ShellLayoutSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
import substitute.presentation.shell.generation_result_workspace_materializer as generation_result_workspace_materializer_module
import substitute.presentation.shell.restore_projection_controller as restore_projection_controller_module
import substitute.presentation.shell.shell_prehydrated_restore_controller as shell_prehydrated_restore_controller_module
import substitute.presentation.shell.shell_layout_restore_controller as shell_layout_restore_controller_module
from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
)
from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
)
from substitute.presentation.shell.generation_result_workspace_materializer import (
    GenerationResultWorkspaceMaterializer,
)
from substitute.presentation.shell.main_window import MainWindow
from substitute.presentation.shell.restore_projection_controller import (
    RestoreProjectionController,
)
from substitute.presentation.shell.shell_workspace_materialization_port import (
    ShellWorkspaceMaterializationPort,
)
from substitute.presentation.shell.workspace_restore_image_adapter import (
    WorkspaceRestoreImageAdapter,
)
from substitute.presentation.shell.shell_layout_restore_controller import (
    ShellLayoutRestoreController,
)
from substitute.presentation.shell.generation_queue_controller import (
    GenerationQueueController,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)


def test_hidden_restore_runtime_prep_hydrates_installs_without_projection_or_layout() -> (
    None
):
    """Hidden restore prep should avoid visible-only projection and layout."""

    view: Any = _restore_view(_workspace())
    events: list[str] = []
    hydrated = _workspace(active_route="wf-a")

    def hydrate(_snapshot: WorkspaceSnapshot, *, operation: str) -> WorkspaceSnapshot:
        """Record hidden hydration and return a hydrated snapshot."""

        events.append(f"hydrate:{operation}")
        return hydrated

    def install(snapshot: WorkspaceSnapshot) -> None:
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

    assert (
        view.shell_prehydrated_restore_controller.prepare_initial_workspace_restore_runtime()
        is True
    )

    assert events == [
        "hydrate:prepare_initial_workspace_restore_runtime",
        "install:wf-a",
    ]
    assert (
        view.shell_prehydrated_restore_controller.prehydrated_restore_runtime_prepared()
        is True
    )
    assert (
        view.shell_prehydrated_restore_controller.prehydrated_restore_finalized()
        is False
    )
    assert view._prehydrated_active_workflow_projection_pending == "wf-a"


def test_prehydrated_input_mask_restore_defers_until_runtime_install() -> None:
    """Prehydration should queue input masks until real workflow state exists."""

    view: Any = _restore_view(_workspace())
    reference = InputMaskReference(
        mask_id=str(uuid4()),
        image_id=str(uuid4()),
        path=Path("mask.png"),
        association_key=("Cube", "load_mask"),
    )

    assert view.workspace_restore_image_adapter.restore_input_mask(reference) is True

    assert view._deferred_prehydrated_input_masks == [reference]


def test_hidden_restore_runtime_replays_deferred_masks_after_install() -> None:
    """Deferred mask restore should run after hydrated workflow state is installed."""

    image_id = UUID("11111111-1111-4111-8111-111111111111")
    snapshot_mask_id = UUID("22222222-2222-4222-8222-222222222222")
    live_mask_id = UUID("33333333-3333-4333-8333-333333333333")
    association_key = ("Cube", "load_mask")
    reference = InputMaskReference(
        mask_id=str(snapshot_mask_id),
        image_id=str(image_id),
        path=Path("mask.png"),
        association_key=association_key,
    )
    hydrated = _workspace_with_input_mask(
        image_id=image_id,
        mask_id=snapshot_mask_id,
        association_key=association_key,
        reference=reference,
    )
    view: Any = _restore_view(hydrated)
    view._deferred_prehydrated_input_masks = [reference]
    events: list[str] = []
    restore_calls: list[dict[str, object]] = []

    def install(snapshot: WorkspaceSnapshot) -> None:
        """Install real workflow state before mask replay."""

        events.append("install")
        view.workflow_session_service = SimpleNamespace(
            workflows={
                workflow_snapshot.workflow_id: workflow_snapshot.workflow
                for workflow_snapshot in snapshot.workflows
            },
        )

    def restore_input_mask(
        workflow_id: str,
        workflow: WorkflowState,
        **kwargs: object,
    ) -> UUID:
        """Record mask replay after workflow install."""

        events.append("restore_mask")
        restore_calls.append(
            {"workflow_id": workflow_id, "workflow": workflow, "kwargs": kwargs}
        )
        return live_mask_id

    def hydrate(
        _snapshot: WorkspaceSnapshot,
        *,
        operation: str,
    ) -> WorkspaceSnapshot:
        """Return the hydrated snapshot for hidden runtime prep."""

        _ = operation
        return hydrated

    view.workspace_restore_controller = SimpleNamespace(
        hydrate_restored_workspace_snapshot=hydrate,
        install_hydrated_prehydrated_workspace=install,
    )
    view.input_canvas_state_service = SimpleNamespace(
        restore_input_mask=restore_input_mask
    )

    assert (
        view.shell_prehydrated_restore_controller.prepare_initial_workspace_restore_runtime()
        is True
    )

    workflow = hydrated.workflows[0].workflow
    assert events == ["install", "restore_mask"]
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
    """Visible finish should apply layout before deferred settings projection."""

    view: Any = _restore_view(_workspace(active_route=SETTINGS_WORKSPACE_ROUTE))
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

    assert (
        view.shell_prehydrated_restore_controller.finish_initial_workspace_restore_layout()
        is True
    )

    assert events == ["project:wf-a", "layout:True", "settings"]
    assert (
        view.shell_prehydrated_restore_controller.prehydrated_restore_finalized()
        is True
    )
    assert view._prehydrated_active_workflow_projection_pending == ""
    assert view._prehydrated_settings_projection_pending is False


def test_pre_show_restore_projection_builds_editor_without_finalizing_layout(
    monkeypatch: MonkeyPatch,
) -> None:
    """Pre-show editor projection should build live widgets and leave layout pending."""

    view: Any = _restore_view(_workspace())
    events: list[str] = []
    view._prehydrated_restore_runtime_prepared = True
    view._prehydrated_active_workflow_projection_pending = "wf-a"
    view.workflow_session_service = _WorkflowSession(events)
    view.generation_action_controller = SimpleNamespace(
        apply_generation_action_availability=lambda: events.append("actions")
    )
    _install_restore_projection_materializer_recorder(monkeypatch, events)
    view.workflow_tabbar = _WorkflowTabbar(events)
    view.cube_stacks = {"wf-a": "cube-stack"}
    view.editor_panels = {"wf-a": "editor-panel"}
    view.cube_stack_container = _StackContainer(events, "cube")
    view.editor_panel_container = _StackContainer(events, "editor")

    def refresh(
        *,
        force_refresh: bool = False,
        on_complete: Callable[[], None],
    ) -> None:
        """Record refresh and finish the pre-show projection."""

        events.append(f"refresh:{force_refresh}")
        on_complete()

    view.active_workflow_surface_refresher = SimpleNamespace(
        refresh_active_workflow_surface=refresh
    )
    artifact = _Artifact(active_workflow_id="wf-a", workflows=(object(),))

    assert view.restore_projection_controller.start_pre_show_restore_projection(
        artifact,
        on_complete=lambda: events.append("complete"),
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
    assert (
        view.shell_prehydrated_restore_controller.prehydrated_restore_finalized()
        is False
    )
    assert view._prehydrated_active_workflow_projection_pending == "wf-a"


def test_pre_show_restore_projection_skips_mismatched_cache_artifact() -> None:
    """Pre-show projection should not run when cache identity does not match."""

    view: Any = _restore_view(_workspace())
    events: list[str] = []
    view._prehydrated_restore_runtime_prepared = True
    view._prehydrated_active_workflow_projection_pending = "wf-a"
    artifact = _Artifact(active_workflow_id="wf-other", workflows=())

    assert not view.restore_projection_controller.start_pre_show_restore_projection(
        artifact,
        on_complete=lambda: events.append("complete"),
    )
    assert events == []


def test_pre_show_restore_projection_uses_live_workflow_without_cache_artifact(
    monkeypatch: MonkeyPatch,
) -> None:
    """Runtime-prepared restores can build the live editor before shell reveal."""

    view: Any = _restore_view(_workspace())
    events: list[str] = []
    view._prehydrated_restore_runtime_prepared = True
    view._prehydrated_active_workflow_projection_pending = "wf-a"
    view.workflow_session_service = _WorkflowSession(events)
    view.generation_action_controller = SimpleNamespace(
        apply_generation_action_availability=lambda: events.append("actions")
    )
    _install_restore_projection_materializer_recorder(monkeypatch, events)
    view.workflow_tabbar = _WorkflowTabbar(events)
    view.cube_stacks = {"wf-a": "cube-stack"}
    view.editor_panels = {"wf-a": "editor-panel"}
    view.cube_stack_container = _StackContainer(events, "cube")
    view.editor_panel_container = _StackContainer(events, "editor")

    def refresh(
        *,
        force_refresh: bool = False,
        on_complete: Callable[[], None],
    ) -> None:
        """Record refresh and finish the pre-show projection."""

        events.append(f"refresh:{force_refresh}")
        on_complete()

    view.active_workflow_surface_refresher = SimpleNamespace(
        refresh_active_workflow_surface=refresh
    )

    assert view.restore_projection_controller.start_pre_show_restore_projection(
        None,
        fallback_workflow_id="wf-a",
        on_complete=lambda: events.append("complete"),
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


def test_restore_split_methods_are_idempotent() -> None:
    """Repeated split restore calls should not duplicate runtime or layout work."""

    view: Any = _restore_view(_workspace())
    events: list[str] = []

    def hydrate(snapshot: WorkspaceSnapshot, *, operation: str) -> WorkspaceSnapshot:
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

    assert (
        view.shell_prehydrated_restore_controller.prepare_initial_workspace_restore_runtime()
        is True
    )
    assert (
        view.shell_prehydrated_restore_controller.prepare_initial_workspace_restore_runtime()
        is True
    )
    assert (
        view.shell_prehydrated_restore_controller.finish_initial_workspace_restore_layout()
        is True
    )
    assert (
        view.shell_prehydrated_restore_controller.finish_initial_workspace_restore_layout()
        is True
    )

    assert events == ["hydrate", "install", "project", "layout"]


def test_finalize_initial_workspace_restore_delegates_to_split_flow() -> None:
    """The public finalize method should preserve the full restore orchestration."""

    view: Any = _restore_view(_workspace())
    events: list[str] = []

    def hydrate(snapshot: WorkspaceSnapshot, *, operation: str) -> WorkspaceSnapshot:
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


def test_materialize_prehydrated_initial_workspace_uses_snapshot_without_hydration(
    monkeypatch: MonkeyPatch,
) -> None:
    """Backend-pending startup should still project saved workflow widgets."""

    snapshot = _workspace()
    view: Any = _restore_view(snapshot)
    events: list[str] = []

    class _Materializer:
        def materialize(self, workspace: WorkspaceSnapshot, port: object) -> object:
            """Record direct snapshot materialization."""

            assert workspace is snapshot
            assert isinstance(port, ShellWorkspaceMaterializationPort)
            events.append("materialize")
            return SimpleNamespace(warnings=("restored output skipped",))

    monkeypatch.setattr(
        shell_prehydrated_restore_controller_module,
        "WorkspaceMaterializationService",
        _Materializer,
    )

    assert (
        view.shell_prehydrated_restore_controller.materialize_prehydrated_initial_workspace()
        is True
    )

    assert events == ["materialize"]
    assert view._prehydrated_workspace_snapshot is snapshot
    assert view._prehydrated_restore_finalized is True
    assert view._initial_workspace_hydrated is True


def test_materialize_prehydrated_initial_workspace_prefers_supplied_restore_snapshot(
    monkeypatch: MonkeyPatch,
) -> None:
    """Backend-pending startup should not materialize placeholder prehydration state."""

    placeholder = _workspace_without_cubes()
    restored = _workspace()
    view: Any = _restore_view(placeholder)
    materialized: list[WorkspaceSnapshot] = []

    class _Materializer:
        def materialize(self, workspace: WorkspaceSnapshot, port: object) -> object:
            """Record direct snapshot materialization."""

            assert isinstance(port, ShellWorkspaceMaterializationPort)
            materialized.append(workspace)
            return SimpleNamespace(warnings=())

    monkeypatch.setattr(
        shell_prehydrated_restore_controller_module,
        "WorkspaceMaterializationService",
        _Materializer,
    )

    assert (
        view.shell_prehydrated_restore_controller.materialize_prehydrated_initial_workspace(
            restored
        )
        is True
    )

    assert materialized == [restored]
    assert view._prehydrated_workspace_snapshot is restored
    assert view._prehydrated_restore_finalized is True


def test_restored_queue_panel_visibility_refreshes_titlebar_segment(
    monkeypatch: MonkeyPatch,
) -> None:
    """Restored side-panel visibility should rederive titlebar queue affordance."""

    view: Any = MainWindow.__new__(MainWindow)
    snapshot = ShellLayoutSnapshot(
        main_splitter_sizes=(1, 2),
        generation_queue_panel_visible=True,
    )
    cluster = _GenerationActionCluster()
    side_panel_host = _SidePanelHost()
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
    view.generation_job_queue_service = _GenerationJobQueueService()
    view.comfy_runtime_actions = SimpleNamespace(
        set_comfy_output_panel_visible=lambda _visible: None
    )
    view.splitter = SimpleNamespace(
        sizes=lambda: [1, 2],
        setSizes=lambda _sizes: None,
        width=lambda: 200,
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
    view.generation_action_controller = GenerationActionController(view)
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
    assert side_panel_host.is_queue_panel_visible() is False

    view.shell_layout_restore_controller.apply_deferred_restored_shell_layout(
        snapshot,
        finalize=False,
    )

    assert side_panel_host.is_queue_panel_visible() is True
    assert cluster.queue_segment_visible_calls == [True, False]


def test_generation_result_workspace_append_hydrates_before_materialization(
    monkeypatch: MonkeyPatch,
) -> None:
    """Queue result replay should append only after runtime restore hydration."""

    view: Any = MainWindow.__new__(MainWindow)
    raw_snapshot = _workspace(active_route="job-raw")
    unique_snapshot = _workspace(active_route="job-open")
    unique_snapshot = WorkspaceSnapshot(
        schema_version=unique_snapshot.schema_version,
        workflows=unique_snapshot.workflows,
        tab_order=unique_snapshot.tab_order,
        active_route=unique_snapshot.active_route,
        active_workflow_id=unique_snapshot.active_workflow_id,
        shell_layout=None,
    )
    hydrated_snapshot = _workspace(active_route="job-hydrated")
    hydrated_snapshot = WorkspaceSnapshot(
        schema_version=hydrated_snapshot.schema_version,
        workflows=hydrated_snapshot.workflows,
        tab_order=hydrated_snapshot.tab_order,
        active_route=hydrated_snapshot.active_route,
        active_workflow_id=hydrated_snapshot.active_workflow_id,
        shell_layout=None,
    )
    events: list[str] = []

    def make_unique(snapshot: WorkspaceSnapshot) -> WorkspaceSnapshot:
        """Record workflow-id uniquing and return the opened-tab snapshot."""

        assert snapshot is raw_snapshot
        events.append("unique")
        return unique_snapshot

    def hydrate(snapshot: WorkspaceSnapshot, *, operation: str) -> WorkspaceSnapshot:
        """Record queue result hydration and return the hydrated snapshot."""

        assert snapshot is unique_snapshot
        assert operation == "materialize_generation_result_workspace"
        assert snapshot.shell_layout is None
        events.append("hydrate")
        return hydrated_snapshot

    class _Materializer:
        """Record the snapshot passed to append materialization."""

        def materialize_into_existing_workspace(
            self,
            snapshot: WorkspaceSnapshot,
            port: object,
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
        _Materializer,
    )

    warnings = view.generation_result_workspace_materializer.materialize_generation_result_workspace(
        raw_snapshot
    )

    assert events == ["unique", "hydrate", "materialize"]
    assert warnings == ("restored output skipped",)


def _restore_view(snapshot: WorkspaceSnapshot) -> Any:
    """Return an uninitialized MainWindow with restore state fields set."""

    view: Any = MainWindow.__new__(MainWindow)
    view.workspace_restore_image_adapter = WorkspaceRestoreImageAdapter(view)
    view.restore_projection_controller = RestoreProjectionController(view)
    view.shell_prehydrated_restore_controller = (
        shell_prehydrated_restore_controller_module.ShellPrehydratedRestoreController(
            view
        )
    )
    view._prehydrated_workspace_snapshot = snapshot
    view._prehydrated_shell_layout = ShellLayoutSnapshot(main_splitter_sizes=(1, 2))
    view._prehydrated_restore_runtime_prepared = False
    view._prehydrated_restore_finalized = False
    view._prehydrated_active_workflow_projection_pending = ""
    view._prehydrated_settings_projection_pending = False
    view._deferred_prehydrated_input_masks = []
    view._shell_restore_lifecycle = "prehydrating"
    view.cube_stack_presentation_controller = SimpleNamespace(
        activate_document_kind=lambda _kind, *, animated: None
    )
    return view


class _Artifact:
    """Tiny projection artifact stand-in for pre-show projection tests."""

    def __init__(
        self,
        *,
        active_workflow_id: str,
        workflows: tuple[object, ...],
    ) -> None:
        """Store fields read by the pre-show projection method."""

        self.active_workflow_id = active_workflow_id
        self.workflows = workflows
        self.cube_definition_fingerprints: dict[str, str] = {}
        self.node_definition_fingerprints: dict[str, str] = {}


class _WorkflowSession:
    """Record workflow activation requests."""

    def __init__(self, events: list[str]) -> None:
        """Store the shared event sink."""

        self._events = events
        self.workflows = {"wf-a": WorkflowState()}

    def activate_workflow(self, workflow_id: str) -> None:
        """Record activation of one workflow."""

        self._events.append(f"activate:{workflow_id}")


class _WorkflowTabbar:
    """Record workflow tab selection requests."""

    def __init__(self, events: list[str]) -> None:
        """Store the shared event sink."""

        self._events = events

    def select_workflow_tab(self, workflow_id: str, *, emit: bool) -> None:
        """Record tab selection."""

        self._events.append(f"tab:{workflow_id}:{emit}")


class _StackContainer:
    """Record stacked-widget current selection requests."""

    def __init__(self, events: list[str], name: str) -> None:
        """Store the shared event sink."""

        self._events = events
        self._name = name

    def setCurrentWidget(self, widget: object) -> None:
        """Record the selected widget."""

        self._events.append(f"{self._name}_current:{widget}")


def _install_restore_projection_materializer_recorder(
    monkeypatch: MonkeyPatch,
    events: list[str],
) -> None:
    """Patch restore projection to record materializer UI hydration."""

    class _Materializer:
        """Record workflow UI hydration requests."""

        def ensure_workflow_ui(
            self,
            workflow_id: str,
            *,
            set_as_current: bool,
        ) -> tuple[object, object]:
            """Record the hydration request."""

            events.append(f"ensure:{workflow_id}:{set_as_current}")
            return object(), object()

    monkeypatch.setattr(
        restore_projection_controller_module,
        "restored_workflow_materializer_for",
        lambda _shell: _Materializer(),
    )


class _GenerationActionCluster:
    """Record generation action availability updates."""

    def __init__(self) -> None:
        """Initialize recorded titlebar queue visibility calls."""

        self.availability_calls: list[dict[str, bool]] = []
        self.queue_badge_count_calls: list[int] = []
        self.queue_segment_visible_calls: list[bool] = []
        self.presentation_calls: list[GenerationActionPresentation] = []
        self.batch_count = 1

    def apply_generation_presentation(
        self,
        presentation: GenerationActionPresentation,
    ) -> None:
        """Record one complete generation action presentation."""

        self.presentation_calls.append(presentation)
        self.availability_calls.append(
            {
                "can_generate": presentation.play_enabled,
                "can_skip": presentation.skip_enabled,
                "can_stop": presentation.stop_enabled,
                "can_show_queue": presentation.queue_primary_enabled,
            }
        )
        self.queue_badge_count_calls.append(presentation.queue_badge_count)
        self.queue_segment_visible_calls.append(presentation.queue_segment_visible)

    def set_batch_count(self, value: int) -> None:
        """Record the titlebar batch count value."""

        self.batch_count = max(1, value)

    def effective_batch_count(self) -> int:
        """Return the normal-generation batch count for controller bindings."""

        return self.batch_count


class _SidePanelHost:
    """Track queue panel visibility for restored layout tests."""

    def __init__(self) -> None:
        """Initialize hidden queue panel state."""

        self._visible = False
        self.panel_widths: list[int] = []

    def is_queue_panel_visible(self) -> bool:
        """Return current fake queue panel visibility."""

        return self._visible

    def set_queue_panel_visible(self, visible: bool) -> None:
        """Apply queue panel visibility to the fake host."""

        self._visible = visible

    def set_panel_width(self, width: int) -> None:
        """Record requested queue panel width."""

        self.panel_widths.append(width)


class _GenerationJobQueueService:
    """Provide empty queue state for generation availability derivation."""

    def has_active_job(self) -> bool:
        """Return whether the fake queue has an active job."""

        return False

    def has_cancellable_jobs(self) -> bool:
        """Return whether the fake queue has cancellable jobs."""

        return False

    def jobs(self) -> tuple[object, ...]:
        """Return visible fake queue jobs."""

        return ()


def _workspace(active_route: str = "wf-a") -> WorkspaceSnapshot:
    """Build a restored workspace snapshot for split restore tests."""

    return WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="wf-a",
                tab_label="A",
                workflow=WorkflowState(
                    cubes={"Cube": _cube()},
                    stack_order=["Cube"],
                ),
                active_cube_alias="Cube",
            ),
        ),
        tab_order=("wf-a",),
        active_route=active_route,
        active_workflow_id="wf-a",
        shell_layout=ShellLayoutSnapshot(main_splitter_sizes=(1, 2)),
    )


def _workspace_without_cubes() -> WorkspaceSnapshot:
    """Build a placeholder workspace snapshot without restored cube state."""

    return WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="wf-a",
                tab_label="A",
                workflow=WorkflowState(),
            ),
        ),
        tab_order=("wf-a",),
        active_route="wf-a",
        active_workflow_id="wf-a",
        shell_layout=ShellLayoutSnapshot(main_splitter_sizes=(1, 2)),
    )


def _workspace_with_input_mask(
    *,
    image_id: UUID,
    mask_id: UUID,
    association_key: tuple[str, str],
    reference: InputMaskReference,
) -> WorkspaceSnapshot:
    """Build a restored workspace snapshot with one canvas mask association."""

    workflow = WorkflowState(
        cubes={"Cube": _cube()},
        stack_order=["Cube"],
    )
    workflow.canvas.input_key_map["Cube:load_image"] = image_id
    workflow.canvas.mask_associations[association_key] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = image_id
    workflow.canvas.active_input_mask_uuid = mask_id
    workflow.canvas.input_image_uuid = image_id
    return WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="wf-a",
                tab_label="A",
                workflow=workflow,
                active_cube_alias="Cube",
                input_masks=(reference,),
            ),
        ),
        tab_order=("wf-a",),
        active_route="wf-a",
        active_workflow_id="wf-a",
        shell_layout=ShellLayoutSnapshot(main_splitter_sizes=(1, 2)),
    )


def _cube() -> CubeState:
    """Build one restored cube."""

    return CubeState(
        cube_id="cube.test",
        version="1.0",
        alias="Cube",
        original_cube={},
        buffer={},
        display_name="Cube",
        ui={},
    )
