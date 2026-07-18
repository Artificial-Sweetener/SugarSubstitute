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

from PySide6.QtCore import QEvent, QEventLoop, QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QWidget

from substitute.application.generation import (
    GenerationRunStarted,
)
from substitute.application.ports import (
    ListenerCompleted,
    OutputImageUpdate,
    PreviewImageUpdate,
)
from substitute.application.workflows import OutputCanvasProjection
from substitute.domain.workflow import WorkflowState
from substitute.presentation.widgets.anchored_row_picker import AnchoredRowPickerView
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

    def __init__(self, *, output_root: Path) -> None:
        """Create a real workspace/canvas shell with fake infrastructure services."""

        self.app = _ensure_qapp()
        self.output_root = output_root
        self.canvas_io_service = _CanvasIoService()
        self.shell = _HarnessShell(self.canvas_io_service)
        self.workflows: dict[str, WorkflowHandle] = {}

    def close(self) -> None:
        """Close real Qt widgets owned by the harness."""

        self.shell.shell_resource_lifecycle.shutdown_or_raise()
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

        safe_source_key = _portable_source_key(spec.source_key)
        path = self.output_root / (
            f"{run.generation_run_id}-{safe_source_key}-{spec.list_index}-"
            f"{spec.batch_index}.png"
        )
        self._emit_output_path(run, spec, path=path, store_image=True)
        return path

    def emit_unloadable_output(
        self,
        run: GenerationRunHandle,
        spec: OutputSpec,
    ) -> Path:
        """Emit a final-output callback whose image path cannot be decoded."""

        safe_source_key = _portable_source_key(spec.source_key)
        path = self.output_root / (
            f"missing-{run.generation_run_id}-{safe_source_key}-{spec.list_index}.png"
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
                batch_index=spec.batch_index,
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

    def output_ids_for_scene_source(
        self,
        *,
        scene_key: str,
        source_key: str,
    ) -> tuple[UUID, ...]:
        """Return projected output IDs for one scene source in batch order."""

        projection = self.shell.output_canvas._output_projection
        if not isinstance(projection, OutputCanvasProjection):
            raise AssertionError("output projection is unavailable")
        scene = next(
            (
                group
                for group in projection.scene_groups
                if group.scene_key == scene_key
            ),
            None,
        )
        if scene is None:
            raise AssertionError(f"output scene is unavailable: {scene_key}")
        source = next(
            (group for group in scene.sources if group.source_key == source_key),
            None,
        )
        if source is None:
            raise AssertionError(f"output source is unavailable: {source_key}")
        return tuple(
            item.image_id for _set_index, item in sorted(source.images_by_set.items())
        )

    def output_representative_id_for_scene(self, scene_key: str) -> UUID:
        """Return the rendered representative image ID for one output scene."""

        projection = self.shell.output_canvas._output_projection
        if not isinstance(projection, OutputCanvasProjection):
            raise AssertionError("output projection is unavailable")
        scene = next(
            (
                group
                for group in projection.scene_groups
                if group.scene_key == scene_key
            ),
            None,
        )
        if (
            scene is None
            or scene.representative_source_key is None
            or scene.representative_set_index is None
        ):
            raise AssertionError(
                f"output scene representative is unavailable: {scene_key}"
            )
        source = next(
            (
                group
                for group in scene.sources
                if group.source_key == scene.representative_source_key
            ),
            None,
        )
        if source is None:
            raise AssertionError(
                f"output scene representative source is unavailable: {scene_key}"
            )
        item = source.images_by_set.get(scene.representative_set_index)
        if item is None:
            raise AssertionError(
                f"output scene representative batch is unavailable: {scene_key}"
            )
        return item.image_id

    def select_output_id(self, image_id: UUID) -> None:
        """Select an Output image through the real widget signal path."""

        self.shell.output_canvas.activeOutputChanged.emit(str(image_id))
        self.process_events()

    def click_canvas_image(self, image_id: UUID) -> None:
        """Click one visible QPane scene image through the production event filter."""

        pane = self.shell.output_canvas.pane
        point = self._canvas_point_for_image(image_id)
        for event_type, buttons in (
            (QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton),
            (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton),
        ):
            local_position = QPointF(point)
            global_position = QPointF(pane.mapToGlobal(point))
            event = QMouseEvent(
                event_type,
                local_position,
                local_position,
                global_position,
                Qt.MouseButton.LeftButton,
                buttons,
                Qt.KeyboardModifier.NoModifier,
            )
            self.app.sendEvent(pane, event)
        self.process_events()

    def click_output_source_tab(self, source_key: str) -> None:
        """Click one rendered Output source tab through its production signal path."""

        tabbar = self.shell.output_canvas.tabbar
        tab_item = tabbar.items.get(source_key)
        if tab_item is None:
            raise AssertionError(
                f"output source tab is unavailable: {source_key}; "
                f"available={tuple(tabbar.items)}"
            )
        tab_item.click()
        self.process_events()

    def _canvas_point_for_image(self, image_id: UUID) -> QPoint:
        """Return a physical QPane point whose public hit identifies an image."""

        pane = self.shell.output_canvas.pane
        hit_test = getattr(pane, "sceneHitTest", None)
        if not callable(hit_test):
            raise AssertionError("output pane does not expose scene hit testing")
        for y in range(2, max(3, pane.height()), 4):
            for x in range(2, max(3, pane.width()), 4):
                point = QPoint(x, y)
                hit = hit_test(point)
                if getattr(hit, "image_id", None) == image_id:
                    return point
        raise AssertionError(
            f"output canvas image is not physically clickable: {image_id}"
        )

    def output_set_picker_keys(self) -> tuple[str, ...]:
        """Open the production set picker and return its visible row keys."""

        self.shell.output_canvas.set_selector_button.click()
        self.process_events()
        return self._visible_output_set_picker().item_keys()

    def select_output_set(self, set_index: int) -> None:
        """Select one batch or grid row through the production popup widget."""

        if not self.shell.output_canvas._set_picker.is_visible():
            self.shell.output_canvas.set_selector_button.click()
            self.process_events()
        picker = self._visible_output_set_picker()
        row = picker.row_for_key(str(set_index))
        if row is None:
            raise AssertionError(
                f"output set picker does not contain row {set_index}: "
                f"{picker.item_keys()}"
            )
        row.click()
        self.process_events()

    def _visible_output_set_picker(self) -> AnchoredRowPickerView:
        """Return the visible production output-set picker view."""

        picker_adapter = self.shell.output_canvas._set_picker
        flyout = picker_adapter._picker._flyout
        if not isinstance(flyout, QWidget):
            raise AssertionError("output set picker flyout is not visible")
        picker = flyout.findChild(AnchoredRowPickerView)
        if picker is None:
            raise AssertionError("output set picker view was not mounted")
        return picker

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


def _portable_source_key(source_key: str) -> str:
    """Return a deterministic filename-safe form of an Output source key."""

    return "".join(
        character if character.isalnum() or character in "-_." else "_"
        for character in source_key
    )
