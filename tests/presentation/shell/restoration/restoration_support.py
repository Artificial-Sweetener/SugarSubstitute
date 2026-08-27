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

"""Provide deterministic fixtures for shell workspace-restoration contracts."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from pytest import MonkeyPatch

from substitute.domain.workflow import CubeState, WorkflowState
from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
)
from substitute.domain.workspace_snapshot import (
    InputMaskReference,
    ShellLayoutSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
import substitute.presentation.shell.restore_projection_controller as restore_projection_controller_module
import substitute.presentation.shell.shell_prehydrated_restore_controller as shell_prehydrated_restore_controller_module
from substitute.presentation.shell.main_window import MainWindow
from substitute.presentation.shell.restore_projection_controller import (
    RestoreProjectionController,
)
from substitute.presentation.shell.workspace_restore_image_adapter import (
    WorkspaceRestoreImageAdapter,
)


def restore_view(snapshot: WorkspaceSnapshot) -> Any:
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
    view.workflow_session_service = SimpleNamespace(workflows={})
    view.restored_ordered_mask_collections = SimpleNamespace(
        reconcile=lambda _workflows: 0
    )
    view.cube_stack_presentation_controller = SimpleNamespace(
        activate_document_kind=lambda _kind, *, animated: None
    )
    return view


class RestoreArtifact:
    """Represent the pre-show projection artifact boundary."""

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


class WorkflowSession:
    """Record workflow activation requests."""

    def __init__(self, events: list[str]) -> None:
        """Store the shared event sink."""

        self._events = events
        self.workflows = {"wf-a": WorkflowState()}

    def activate_workflow(self, workflow_id: str) -> None:
        """Record activation of one workflow."""

        self._events.append(f"activate:{workflow_id}")


class WorkflowTabbar:
    """Record workflow tab selection requests."""

    def __init__(self, events: list[str]) -> None:
        """Store the shared event sink."""

        self._events = events

    def select_workflow_tab(self, workflow_id: str, *, emit: bool) -> None:
        """Record tab selection."""

        self._events.append(f"tab:{workflow_id}:{emit}")


class StackContainer:
    """Record stacked-widget current selection requests."""

    def __init__(self, events: list[str], name: str) -> None:
        """Store the shared event sink."""

        self._events = events
        self._name = name

    def setCurrentWidget(self, widget: object) -> None:
        """Record the selected widget."""

        self._events.append(f"{self._name}_current:{widget}")


def install_restore_projection_materializer_recorder(
    monkeypatch: MonkeyPatch,
    events: list[str],
) -> None:
    """Patch restore projection to record materializer UI hydration."""

    class Materializer:
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
        lambda _shell: Materializer(),
    )


def prepared_projection_view(monkeypatch: MonkeyPatch, events: list[str]) -> Any:
    """Build a runtime-prepared restore view that records editor projection."""

    view = restore_view(workspace())
    view._prehydrated_restore_runtime_prepared = True
    view._prehydrated_active_workflow_projection_pending = "wf-a"
    view.workflow_session_service = WorkflowSession(events)
    view.generation_action_controller = SimpleNamespace(
        apply_generation_action_availability=lambda: events.append("actions")
    )
    install_restore_projection_materializer_recorder(monkeypatch, events)
    view.workflow_tabbar = WorkflowTabbar(events)
    view.cube_stacks = {"wf-a": "cube-stack"}
    view.editor_panels = {"wf-a": "editor-panel"}
    view.cube_stack_container = StackContainer(events, "cube")
    view.editor_panel_container = StackContainer(events, "editor")

    def refresh(
        *, force_refresh: bool = False, on_complete: Callable[[], None]
    ) -> None:
        """Record refresh and complete the projection."""

        events.append(f"refresh:{force_refresh}")
        on_complete()

    view.active_workflow_surface_refresher = SimpleNamespace(
        refresh_active_workflow_surface=refresh
    )
    return view


def workspace(active_route: str = "wf-a") -> WorkspaceSnapshot:
    """Build a restored workspace snapshot for split restore tests."""

    return WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="wf-a",
                tab_label="A",
                workflow=WorkflowState(
                    cubes={"Cube": cube()},
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


def workspace_without_cubes() -> WorkspaceSnapshot:
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


def workspace_with_input_mask(
    *,
    image_id: UUID,
    mask_id: UUID,
    association_key: tuple[str, str],
    reference: InputMaskReference,
) -> WorkspaceSnapshot:
    """Build a restored workspace snapshot with one canvas mask association."""

    current_workflow = WorkflowState(
        cubes={"Cube": cube()},
        stack_order=["Cube"],
    )
    current_workflow.canvas.bind_image("Cube:load_image", image_id)
    current_workflow.canvas.bind_mask(association_key, mask_id, image_id)
    current_workflow.canvas.active_input_mask_uuid = mask_id
    current_workflow.canvas.input_image_uuid = image_id
    return WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="wf-a",
                tab_label="A",
                workflow=current_workflow,
                active_cube_alias="Cube",
                input_masks=(reference,),
            ),
        ),
        tab_order=("wf-a",),
        active_route="wf-a",
        active_workflow_id="wf-a",
        shell_layout=ShellLayoutSnapshot(main_splitter_sizes=(1, 2)),
    )


def cube() -> CubeState:
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


class GenerationActionCluster:
    """Record generation action availability updates."""

    def __init__(self) -> None:
        """Initialize recorded titlebar queue visibility calls."""

        self.availability_calls: list[dict[str, bool]] = []
        self.queue_badge_count_calls: list[int] = []
        self.queue_segment_visible_calls: list[bool] = []
        self.presentation_calls: list[GenerationActionPresentation] = []
        self.batch_count = 1

    def apply_generation_presentation(
        self, presentation: GenerationActionPresentation
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


class SidePanelHost:
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


class GenerationJobQueueService:
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
