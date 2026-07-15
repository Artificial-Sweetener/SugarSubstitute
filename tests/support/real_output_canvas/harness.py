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

"""Drive real-shell Output canvas scenarios through user-level operations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QEventLoop, QRectF, QTimer

from substitute.application.generation import (
    GenerationRunStarted,
)
from substitute.application.ports import (
    ListenerCompleted,
    OutputImageUpdate,
    PreviewImageUpdate,
)
from substitute.domain.workflow import WorkflowState
from tests.support.real_output_canvas.assertions import (
    collect_canvas_fingerprint,
)
from tests.support.real_output_canvas.models import (
    CanvasFingerprint,
    GenerationRunHandle,
    OutputSpec,
    WorkflowHandle,
    solid_image,
)
from tests.support.real_output_canvas.shell import (
    _CanvasIoService,
    _HarnessShell,
    _ensure_qapp,
)


class RealShellOutputCanvasHarness:
    """Drive real shell Output canvas collaborators from fake Comfy callbacks."""

    def __init__(self) -> None:
        """Create a real workspace/canvas shell with fake infrastructure services."""

        self.app = _ensure_qapp()
        self.canvas_io_service = _CanvasIoService()
        self.shell = _HarnessShell(self.canvas_io_service)
        self.workflows: dict[str, WorkflowHandle] = {}

    def close(self) -> None:
        """Close real Qt widgets owned by the harness."""

        self.shell.close()
        self.shell.execution_runtime.shutdown()
        self.process_events()

    def add_workflow(self, alias: str, *, activate: bool = False) -> WorkflowHandle:
        """Add one workflow to the real session and tab bar."""

        workflow_id = f"workflow-{alias}"
        workflow = WorkflowState(metadata={"name": alias})
        if not self.workflows:
            self.shell.workflow_session_service.replace_workflows(
                {workflow_id: workflow},
                active_workflow_id=workflow_id,
            )
        else:
            self.shell.workflow_session_service.add_existing_workflow(
                workflow_id,
                workflow,
                activate=activate,
            )
        self.shell.workflow_tabbar.addTab(workflow_id, alias)
        self.shell.install_workflow_surface(workflow_id)
        handle = WorkflowHandle(alias=alias, workflow_id=workflow_id)
        self.workflows[alias] = handle
        if activate or len(self.workflows) == 1:
            self.activate_workflow(alias)
        return handle

    def activate_workflow(self, alias: str) -> None:
        """Activate one workflow through the production workflow coordinator."""

        workflow_id = self.workflows[alias].workflow_id
        self.shell.workflow_workspace.activate_workflow(
            workflow_id,
            source="workflow_tab",
        )
        self.process_events()

    def project_workflow_directly(self, alias: str) -> None:
        """Project one workflow through the narrow Output coordinator only."""

        workflow_id = self.workflows[alias].workflow_id
        self.shell.workflow_session_service.activate_workflow(workflow_id)
        self.shell.output_canvas_projection_coordinator.project_workflow(
            self.shell.workflow_session_service.workflows,
            workflow_id,
        )
        self.process_events()

    def show_canvas(self, label: str) -> None:
        """Select a real canvas tab route."""

        self.shell.canvas_tabs.focus_attached_canvas(label)
        self.process_events()

    def start_run(self, alias: str, run_index: int = 1) -> GenerationRunHandle:
        """Register an authorized generation run through dispatcher ingress."""

        workflow = self.workflows[alias]
        run = GenerationRunHandle(
            workflow=workflow,
            generation_run_id=f"{workflow.workflow_id}-run-{run_index}",
            prompt_id=f"{workflow.workflow_id}-prompt-{run_index}",
            client_id=f"{workflow.workflow_id}-client-{run_index}",
        )
        self.shell.generation_feedback_dispatcher.on_run_started(
            GenerationRunStarted(
                workflow_id=workflow.workflow_id,
                generation_run_id=run.generation_run_id,
                prompt_id=run.prompt_id,
                client_id=run.client_id,
            )
        )
        self.process_events()
        self.shell.generation_feedback_dispatcher.flush_now()
        self.process_events()
        return run

    def emit_output(self, run: GenerationRunHandle, spec: OutputSpec) -> Path:
        """Emit one fake Comfy final-output callback into the real dispatcher."""

        path = Path(
            f"E:/devprojects/SugarSubstitute/.tmp-output-canvas/"
            f"{run.generation_run_id}-{spec.source_key}-{spec.list_index}.png"
        )
        self._emit_output_path(run, spec, path=path, store_image=True)
        return path

    def emit_unloadable_output(
        self,
        run: GenerationRunHandle,
        spec: OutputSpec,
    ) -> Path:
        """Emit a final-output callback whose image path cannot be decoded."""

        path = Path(
            f"E:/devprojects/SugarSubstitute/.tmp-output-canvas/"
            f"missing-{run.generation_run_id}-{spec.source_key}-{spec.list_index}.png"
        )
        self._emit_output_path(run, spec, path=path, store_image=False)
        return path

    def _emit_output_path(
        self,
        run: GenerationRunHandle,
        spec: OutputSpec,
        *,
        path: Path,
        store_image: bool,
    ) -> None:
        """Submit one output callback with optional fake loader backing."""

        if store_image:
            self.canvas_io_service.store_image(
                path,
                solid_image(spec.color, width=spec.width, height=spec.height),
            )
        scene = spec.scene
        self.shell.generation_feedback_dispatcher.on_output_image(
            OutputImageUpdate(
                workflow_id=run.workflow.workflow_id,
                workflow_payload={
                    spec.node_id: {"_meta": {"title": spec.source_label}},
                },
                file_path=path,
                node_id=spec.node_id,
                generation_run_id=run.generation_run_id,
                prompt_id=run.prompt_id,
                client_id=run.client_id,
                source_key=spec.source_key,
                source_label=spec.source_label,
                list_index=spec.list_index,
                artifact_width=spec.width,
                artifact_height=spec.height,
                scene_run_id=None if scene is None else scene.run_id,
                scene_key=None if scene is None else scene.key,
                scene_title=None if scene is None else scene.title,
                scene_order=None if scene is None else scene.order,
                scene_count=None if scene is None else scene.count,
            )
        )

    def emit_preview(self, run: GenerationRunHandle, spec: OutputSpec) -> None:
        """Emit one fake Comfy preview callback into the real dispatcher."""

        scene = spec.scene
        self.shell.generation_feedback_dispatcher.on_preview(
            PreviewImageUpdate(
                workflow_id=run.workflow.workflow_id,
                image=solid_image(spec.color, width=spec.width, height=spec.height),
                generation_run_id=run.generation_run_id,
                prompt_id=run.prompt_id,
                client_id=run.client_id,
                node_id=spec.node_id,
                metadata_node_id=spec.node_id,
                display_node_id=spec.node_id,
                parent_node_id=spec.node_id,
                real_node_id=spec.node_id,
                source_key=spec.source_key,
                source_label=spec.source_label,
                scene_run_id=None if scene is None else scene.run_id,
                scene_key=None if scene is None else scene.key,
                scene_title=None if scene is None else scene.title,
                scene_order=None if scene is None else scene.order,
                scene_count=None if scene is None else scene.count,
            )
        )

    def complete_run(self, run: GenerationRunHandle) -> None:
        """Emit one fake Comfy completion callback into the real dispatcher."""

        self.shell.generation_feedback_dispatcher.on_completed(
            ListenerCompleted(
                workflow_id=run.workflow.workflow_id,
                generation_run_id=run.generation_run_id,
                prompt_id=run.prompt_id,
            )
        )
        self.process_events()
        self.shell.generation_feedback_dispatcher.flush_now()
        self.process_events()

    def wait_for_output_count(self, alias: str, count: int) -> None:
        """Wait until a workflow has registered count Output images."""

        workflow_id = self.workflows[alias].workflow_id
        self.wait_until(
            lambda: (
                len(
                    self.shell.workflow_session_service.workflows[
                        workflow_id
                    ].output_image_uuids
                )
                == count
            )
        )

    def output_count(self, alias: str) -> int:
        """Return the number of registered outputs for one workflow."""

        workflow_id = self.workflows[alias].workflow_id
        return len(
            self.shell.workflow_session_service.workflows[
                workflow_id
            ].output_image_uuids
        )

    def output_ids(self, alias: str) -> tuple[UUID, ...]:
        """Return registered Output image IDs for one workflow."""

        workflow_id = self.workflows[alias].workflow_id
        return tuple(
            self.shell.workflow_session_service.workflows[
                workflow_id
            ].output_image_uuids
        )

    def select_output_id(self, image_id: UUID) -> None:
        """Select an Output image through the real widget signal path."""

        self.shell.output_canvas.activeOutputChanged.emit(str(image_id))
        self.process_events()

    def clear_output_for(self, alias: str) -> None:
        """Clear workflow Output through the real shell signal path."""

        workflow_id = self.workflows[alias].workflow_id
        self.shell.clear_output_signal.emit(workflow_id)
        self.process_events()

    def close_workflow(self, alias: str) -> None:
        """Close one workflow through the real workspace coordinator."""

        workflow_id = self.workflows[alias].workflow_id
        self.shell.workflow_workspace.close_workflow(workflow_id)
        self.workflows.pop(alias, None)
        self.process_events()

    def rename_workflow(self, alias: str, new_alias: str) -> WorkflowHandle:
        """Rename one workflow through the real workspace coordinator."""

        old_handle = self.workflows[alias]
        self.shell.workflow_workspace.rename_workflow(
            old_handle.workflow_id,
            new_alias,
        )
        self.process_events()
        new_handle = WorkflowHandle(alias=new_alias, workflow_id=new_alias)
        self.workflows.pop(alias, None)
        self.workflows[new_alias] = new_handle
        return new_handle

    def preview_count(self) -> int:
        """Return the number of transient Output preview lanes."""

        return len(self.shell.output_preview_registry.lanes_for_session_like())

    def wait_for_preview_count(self, count: int) -> None:
        """Wait until the transient Output preview registry reaches count lanes."""

        self.wait_until(lambda: self.preview_count() == count)

    def drain_events_for(self, duration_ms: int) -> None:
        """Process Qt events for a short fixed duration."""

        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.start(duration_ms)
        while deadline.isActive():
            self.process_events(cycles=2)
            loop = QEventLoop()
            QTimer.singleShot(10, loop.quit)
            loop.exec()
        self.process_events(cycles=4)

    def wait_until(
        self,
        predicate: Callable[[], object],
        *,
        timeout_ms: int = 2500,
    ) -> None:
        """Process Qt events until predicate succeeds or the timeout expires."""

        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.start(timeout_ms)
        while not bool(predicate()):
            if not deadline.isActive():
                raise AssertionError(f"timed out waiting for {predicate!r}")
            self.process_events(cycles=2)
            loop = QEventLoop()
            QTimer.singleShot(10, loop.quit)
            loop.exec()
        self.process_events(cycles=4)

    def process_events(self, *, cycles: int = 4) -> None:
        """Let queued Qt signals, timers, and worker completions run."""

        for _index in range(cycles):
            self.app.processEvents()

    def set_output_viewport_extent(
        self,
        width: float,
        height: float,
        *,
        settle_ms: int = 30,
    ) -> None:
        """Deliver one physical QPane viewport extent and process its reflow frame."""

        self.shell.output_canvas.pane.viewportRectChanged.emit(
            QRectF(0.0, 0.0, width, height)
        )
        self.drain_events_for(settle_ms)

    def fingerprint(self) -> CanvasFingerprint:
        """Capture the real Output QPane and workflow state."""

        return collect_canvas_fingerprint(self.shell)

    def assert_showing_workflow(
        self,
        alias: str,
        *,
        color: tuple[int, int, int] | None = None,
    ) -> None:
        """Assert the real Output pane displays the workflow's active image."""

        workflow_id = self.workflows[alias].workflow_id
        workflow = self.shell.workflow_session_service.workflows[workflow_id]
        self.wait_until(
            lambda: (
                self.fingerprint().pane_current_image_id == workflow.active_output_uuid
            )
        )
        state = self.fingerprint()
        assert workflow.active_output_uuid is not None, state
        assert state.pane_current_image_id == workflow.active_output_uuid, state
        assert workflow.active_output_uuid in state.pane_image_ids, state
        assert not state.current_image_is_null, state
        if color is not None:
            assert state.current_image_rgb == color, state

    def assert_not_showing_workflow(self, alias: str) -> None:
        """Assert the real Output pane is not routed to a workflow's outputs."""

        workflow_id = self.workflows[alias].workflow_id
        workflow_image_ids = set(
            self.shell.workflow_session_service.workflows[
                workflow_id
            ].output_image_uuids
        )
        state = self.fingerprint()
        assert state.pane_current_image_id not in workflow_image_ids, state
        assert not workflow_image_ids.intersection(state.composition_image_ids), state

    def assert_scene_composition_for_workflow(self, alias: str) -> None:
        """Assert the active Output route is a scene composition for a workflow."""

        workflow_id = self.workflows[alias].workflow_id
        expected = set(
            self.shell.workflow_session_service.workflows[
                workflow_id
            ].output_image_uuids
        )
        self.wait_until(
            lambda: (
                self.fingerprint().pane_current_composition_id is not None
                and bool(
                    expected.intersection(self.fingerprint().composition_image_ids)
                )
            )
        )
        state = self.fingerprint()
        assert state.pane_current_composition_id is not None, state
        assert expected.intersection(state.composition_image_ids), state
        assert set(state.composition_image_ids) <= expected, state

    def assert_preview_displayed(
        self,
        *,
        color: tuple[int, int, int],
    ) -> None:
        """Assert the real Output pane is currently displaying a preview image."""

        self.wait_until(
            lambda: (
                self.fingerprint().pane_current_image_id
                in self.fingerprint().preview_image_ids
                and self.fingerprint().current_image_rgb == color
            )
        )
        state = self.fingerprint()
        assert state.pane_current_image_id in state.preview_image_ids, state
        assert not state.current_image_is_null, state
        assert state.current_image_rgb == color, state

    def assert_no_previews(self) -> None:
        """Assert no transient preview lanes remain registered or displayed."""

        state = self.fingerprint()
        assert not state.preview_image_ids, state
        assert not state.preview_lane_keys, state
        assert state.pane_current_image_id not in state.preview_image_ids, state
