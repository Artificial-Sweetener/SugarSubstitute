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

"""Characterization tests for canvas projection coordinator behavior."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.input_canvas_state_service import (
    InputCanvasStateService,
)
from substitute.application.workflows.output_canvas_projection_coordinator import (
    OutputCanvasProjectionCoordinator,
    OutputProjectionCatalogWarmer,
    OutputProjectionPayloadHydrator,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_canvas_state_service import (
    OutputCanvasStateService,
)
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    OutputVisualIdentity,
    SourceOnlyOutputIdentity,
)
from substitute.domain.workflow import (
    CanvasSessionBoundary,
    CanvasKind,
    ImageMeta,
    OutputCompareSelection,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)
from substitute.domain.generation import OutputResultPosition
from substitute.presentation.canvas.qpane import (
    CanvasPaneCatalog,
    InputQPaneRouteAdapter,
    InputRouteProjector,
    OutputQPaneRouteAdapter,
    OutputRouteProjector,
)
from substitute.presentation.shell.canvas_projection_scheduler import (
    CanvasProjectionScheduler,
)
from substitute.presentation.shell.output_image_commit_pipeline import (
    OutputImageCommitRequest,
    PreparedOutputImage,
)
from substitute.presentation.shell.output_image_commit_queue import (
    PreparedOutputCommitQueue,
)


class _FakePane:
    def __init__(self):
        self.images = {}
        self.add_calls = []
        self.current_id = None
        self.selection_calls = []
        self.active_mask = None
        self.linked_groups = ()
        self.next_loaded_mask_id = None
        self.next_blank_mask_id = uuid.uuid4()
        self.removed_masks = []
        self.updated_masks = []
        self.mask_controller = self

    def setLinkedGroups(self, groups):
        self.linked_groups = tuple(groups)

    def setCurrentImageID(self, image_id):
        self.selection_calls.append(image_id)
        self.current_id = image_id

    def currentImageID(self):
        return self.current_id

    def addImage(self, image_id, image, path):
        self.add_calls.append((image_id, image, path))
        self.images[image_id] = (image, path)

    def removeImageByID(self, image_id):
        self.images.pop(image_id, None)

    def imageIDs(self):
        return list(self.images)

    def getCatalogSnapshot(self):
        return SimpleNamespace(
            catalog={
                image_id: SimpleNamespace(image=image, path=path)
                for image_id, (image, path) in self.images.items()
            },
        )

    def createBlankMask(self, _size):
        return self.next_blank_mask_id

    def setActiveMaskID(self, mask_id):
        self.active_mask = mask_id

    def loadMaskFromFile(self, _path):
        return self.next_loaded_mask_id

    def removeMaskFromImage(self, image_id, mask_id):
        self.removed_masks.append((image_id, mask_id))
        return True

    def update_mask_from_file(self, mask_id, path):
        self.updated_masks.append((mask_id, path))
        return True


class _FakeOutputCanvas:
    def __init__(self):
        self.events = []
        self.sync_calls = []
        self.sync_session_calls = []
        self.register_calls = []
        self.clear_preview_calls = []
        self.prepare_calls = []

    def bind_projection_session(self, session):
        projection = session.projection
        image_ids = tuple(
            item.image_id
            for source in projection.sources
            for item in source.images_by_set.values()
        )
        workflow_id = session.workflow_id.value
        self.events.append(("bind", workflow_id))
        self.prepare_calls.append((workflow_id, image_ids))
        self.sync_session_calls.append(session)
        self.sync_calls.append(projection)

    def clear_previews(self, source_key=None):
        self.events.append(("clear_previews", source_key))
        self.clear_preview_calls.append(source_key)


class _FakeLinkedGroupSink:
    def __init__(self, pane: _FakePane) -> None:
        self._pane = pane

    def present_linked_outputs(self, output_image_ids: tuple[uuid.UUID, ...]) -> None:
        members = tuple(dict.fromkeys(output_image_ids))
        if len(members) < 2:
            self._pane.setLinkedGroups(())
            return
        self._pane.setLinkedGroups(
            (SimpleNamespace(group_id=uuid.uuid4(), members=members),)
        )


class _CanvasProjectionHarness:
    def __init__(
        self,
        *,
        image_registry: CanvasImageRegistry,
        canvas_session_boundary: CanvasSessionBoundary,
        output_canvas_state_service: OutputCanvasStateService,
        input_canvas_state_service: InputCanvasStateService,
        output_canvas_projection_coordinator: OutputCanvasProjectionCoordinator,
    ) -> None:
        self.image_registry = image_registry
        self.canvas_session_boundary = canvas_session_boundary
        self.output_canvas_state_service = output_canvas_state_service
        self._input_canvas_state_service = input_canvas_state_service
        self._output_canvas_projection_coordinator = (
            output_canvas_projection_coordinator
        )

    def project_workflow(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
    ) -> None:
        self._input_canvas_state_service.project_workflow(
            workflows,
            active_workflow_id,
        )
        self._output_canvas_projection_coordinator.project_workflow(
            workflows,
            active_workflow_id,
        )

    def project_output(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
        *,
        registered_image_id: uuid.UUID | None = None,
    ) -> None:
        self._output_canvas_projection_coordinator.project_workflow(
            workflows,
            active_workflow_id,
            registered_image_id=registered_image_id,
        )

    def clear_output_for_workflow(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
    ) -> None:
        self._output_canvas_projection_coordinator.clear_output_for_workflow(
            workflows,
            active_workflow_id,
        )

    def prune_closed_workflow_images(
        self,
        closed_workflow_id: str,
        closed_workflow: WorkflowState,
        remaining_workflows: Mapping[str, WorkflowState],
    ) -> None:
        self._output_canvas_projection_coordinator.prune_closed_workflow_images(
            closed_workflow_id,
            closed_workflow,
            remaining_workflows,
        )


def _build_services() -> tuple[
    _CanvasProjectionHarness,
    InputCanvasStateService,
    _FakePane,
    _FakePane,
    _FakeOutputCanvas,
]:
    input_pane = _FakePane()
    output_pane = _FakePane()
    output_canvas = _FakeOutputCanvas()
    canvas_session_boundary = CanvasSessionBoundary()
    image_registry = CanvasImageRegistry()
    input_canvas_state_service = InputCanvasStateService(
        input_pane=input_pane,
        input_catalog=CanvasPaneCatalog(input_pane),
        input_route_projector=InputRouteProjector(
            InputQPaneRouteAdapter(input_pane),
            session_boundary=canvas_session_boundary,
        ),
        canvas_session_boundary=canvas_session_boundary,
        image_registry=image_registry,
    )
    output_catalog = CanvasPaneCatalog(output_pane)
    output_canvas_state_service = OutputCanvasStateService(
        image_registry=image_registry,
    )
    output_canvas_projection_coordinator = OutputCanvasProjectionCoordinator(
        image_registry=image_registry,
        output_canvas_state_service=output_canvas_state_service,
        output_route_projector=OutputRouteProjector(
            OutputQPaneRouteAdapter(output_pane),
            session_boundary=canvas_session_boundary,
        ),
        canvas_session_boundary=canvas_session_boundary,
        catalog_warmer=OutputProjectionCatalogWarmer(
            image_registry=image_registry,
            output_catalog=output_catalog,
        ),
        payload_hydrator=OutputProjectionPayloadHydrator(
            image_registry=image_registry,
            output_catalog=output_catalog,
        ),
        projection_sink=output_canvas,
        linked_group_sink=_FakeLinkedGroupSink(output_pane),
    )
    service = _CanvasProjectionHarness(
        image_registry=image_registry,
        canvas_session_boundary=canvas_session_boundary,
        output_canvas_state_service=output_canvas_state_service,
        input_canvas_state_service=input_canvas_state_service,
        output_canvas_projection_coordinator=output_canvas_projection_coordinator,
    )
    return service, input_canvas_state_service, input_pane, output_pane, output_canvas


def _build_service():
    service, _input_service, input_pane, output_pane, output_canvas = _build_services()
    return service, input_pane, output_pane, output_canvas


def _app() -> QApplication:
    """Return a QApplication for Qt-backed scheduler tests."""

    app = QCoreApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _store_image_record(
    service: _CanvasProjectionHarness,
    image_id: uuid.UUID,
    image_meta: ImageMeta,
    *,
    payload: object | None = None,
) -> None:
    """Store a test image record through the shared registry."""

    service.image_registry.store(image_id, payload=payload, metadata=image_meta)


def _add_output_image(
    service: _CanvasProjectionHarness,
    workflows: dict[str, WorkflowState],
    *,
    origin_workflow_id: str,
    active_workflow_id: str,
    image: object,
    image_meta: ImageMeta,
) -> uuid.UUID:
    """Register and project an output image through Phase 7 owners."""

    result = service.output_canvas_state_service.register_output_image(
        workflows,
        origin_workflow_id,
        active_workflow_id,
        image,
        image_meta,
    )
    assert result.image_id is not None
    if result.projection_intent.should_schedule:
        service.project_output(
            workflows,
            active_workflow_id,
            registered_image_id=result.projection_intent.registered_image_id,
        )
    return result.image_id


def _live_final_event() -> LiveFinalOutputEvent:
    """Build one strict live final event for generated-output registration tests."""

    return LiveFinalOutputEvent(
        identity=OutputVisualIdentity(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            source_key="wf:node",
            source_label="Cube",
            scene=SourceOnlyOutputIdentity(),
        ),
        node_id="node",
        workflow_payload={"node": {"class_type": "SugarCubes.CubeOutput"}},
        file_path=Path("E:/out.png"),
        position=OutputResultPosition(list_index=0, batch_index=0),
        artifact_width=640,
        artifact_height=480,
    )


def test_update_canvases_for_missing_workflow_clears_pane_selections() -> None:
    """Missing active workflow deselects panes and clears output tabs."""
    service, input_pane, output_pane, output_canvas = _build_service()
    input_pane.current_id = uuid.uuid4()
    output_pane.current_id = uuid.uuid4()

    service.project_workflow({}, "missing")

    assert input_pane.selection_calls == [None]
    assert output_pane.selection_calls == [None]
    assert input_pane.current_id is None
    assert output_pane.current_id is None
    assert output_pane.linked_groups == ()
    assert output_canvas.clear_preview_calls == [None]
    assert output_canvas.sync_calls[-1].sources == ()
    input_session = service.canvas_session_boundary.current_session(CanvasKind.INPUT)
    output_session = service.canvas_session_boundary.current_session(CanvasKind.OUTPUT)
    assert input_session is not None
    assert input_session.active_route.route_kind == "empty"
    assert output_session is not None
    assert output_session.active_route.route_kind == "empty"


def test_restore_input_image_preserves_snapshot_uuid() -> None:
    """Input restore should insert the provided UUID without generating a new one."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    image_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    path = Path("input.png")

    input_service.restore_input_image(image_id=image_id, image="input-image", path=path)

    assert input_pane.images == {image_id: ("input-image", path)}


def test_restore_input_image_skips_existing_identical_payload() -> None:
    """Input restore should not re-add an unchanged catalog payload."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    image_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    path = Path("input.png")
    image = object()

    input_service.restore_input_image(image_id=image_id, image=image, path=path)
    input_service.restore_input_image(image_id=image_id, image=image, path=path)

    assert input_pane.add_calls == [(image_id, image, path)]


def test_restore_output_image_preserves_snapshot_uuid_and_metadata() -> None:
    """Output restore should hydrate registry state under the provided UUID."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    image_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    image_meta = ImageMeta(
        workflow_name="Workflow",
        cube_name="Save",
        image_number=1,
        suffix="",
        path="output.png",
    )

    service.output_canvas_state_service.restore_output_image(
        workflow_id="wf",
        image_id=image_id,
        image="output-image",
        image_meta=image_meta,
    )

    assert output_pane.images == {}
    assert service.image_registry.metadata_for(image_id) is image_meta
    assert service.image_registry.payload_for(image_id) == "output-image"
    assert output_canvas.register_calls == []


def test_apply_output_source_timing_updates_existing_output_metadata() -> None:
    """Timing enrichment should update existing output metadata without new image ids."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    workflows = {"wf": workflow}
    image_meta = ImageMeta(
        workflow_name="Workflow",
        cube_name="Cube",
        image_number=1,
        suffix="",
        path="output.png",
        source_key="wf:save",
        source_label="Cube",
    )
    result = service.output_canvas_state_service.register_output_image(
        workflows,
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image="output-image",
        image_meta=image_meta,
    )

    changed = service.output_canvas_state_service.apply_output_source_timing(
        workflows,
        workflow_id="wf",
        active_workflow_id="wf",
        source_durations_ms={"wf:save": 3080.0},
        cube_durations_ms={},
    )

    assert changed.changed is True
    assert changed.projection_intent.should_schedule is True
    assert workflow.output_image_uuids == [result.image_id]
    stored_meta = service.image_registry.metadata_for(result.image_id)
    assert stored_meta is not None
    assert stored_meta.cube_execution_duration_ms == 3080.0
    assert output_canvas.sync_calls == []


def test_load_input_image_replaces_previous_unreferenced_uuid() -> None:
    """Replacing an input key removes old UUID when no workflow still references it."""
    service, input_service, input_pane, _output_pane, _output_canvas = _build_services()
    workflow = WorkflowState()
    old_id = uuid.uuid4()
    workflow.canvas.input_key_map["A:node"] = old_id
    workflow.canvas.input_image_uuid = old_id
    input_pane.images[old_id] = ("old", Path("old.png"))
    _store_image_record(service, old_id, ImageMeta("wf", "Cube", 1, "", ""))

    new_id = input_service.load_input_image(
        {"wf": workflow},
        "wf",
        "A:node",
        image=object(),
        path=Path("new.png"),
    )

    assert old_id not in input_pane.images
    assert service.image_registry.metadata_for(old_id) is None
    assert workflow.canvas.input_key_map["A:node"] == new_id
    assert workflow.canvas.input_image_uuid == new_id
    assert input_pane.current_id == new_id


def test_load_input_image_keeps_previous_uuid_when_still_referenced_elsewhere() -> None:
    """Replacing input UUID should retain old UUID when another workflow still references it."""
    service, input_service, input_pane, _output_pane, _output_canvas = _build_services()
    workflow_a = WorkflowState()
    workflow_b = WorkflowState()
    old_id = uuid.uuid4()
    workflow_a.canvas.input_key_map["A:node"] = old_id
    workflow_a.canvas.input_image_uuid = old_id
    workflow_b.output_image_uuids = [old_id]
    input_pane.images[old_id] = ("old", Path("old.png"))
    _store_image_record(service, old_id, ImageMeta("wf", "Cube", 1, "", ""))

    _ = input_service.load_input_image(
        {"A": workflow_a, "B": workflow_b},
        "A",
        "A:node",
        image=object(),
        path=Path("new.png"),
    )

    assert old_id in input_pane.images
    assert service.image_registry.metadata_for(old_id) is not None


def test_add_output_image_refreshes_only_visible_workflow() -> None:
    """Output UI is refreshed only when the origin workflow is currently active."""
    service, _input_pane, output_pane, output_canvas = _build_service()
    wf_a = WorkflowState()
    wf_b = WorkflowState()
    workflows = {"A": wf_a, "B": wf_b}

    _add_output_image(
        service,
        workflows,
        origin_workflow_id="B",
        active_workflow_id="A",
        image=object(),
        image_meta=ImageMeta("wfB", "CubeB", 1, "", ""),
    )
    assert wf_b.output_image_uuids
    assert output_canvas.sync_calls == []
    assert output_canvas.register_calls == []

    active_image = object()
    _add_output_image(
        service,
        workflows,
        origin_workflow_id="A",
        active_workflow_id="A",
        image=active_image,
        image_meta=ImageMeta("wfA", "CubeA", 2, "", ""),
    )
    assert wf_a.output_image_uuids
    assert output_canvas.register_calls == []
    assert output_pane.images[wf_a.output_image_uuids[-1]][0] is active_image
    assert output_canvas.prepare_calls[-1][1] == (wf_a.output_image_uuids[-1],)
    assert (
        service.image_registry.payload_for(wf_a.output_image_uuids[-1]) is active_image
    )
    assert output_canvas.sync_calls, "Visible workflow output should sync projection"


def test_project_workflow_preserves_input_and_output_catalog_membership() -> None:
    """Phase 0 - Input/Output switching keeps QPane catalogs as cache membership."""

    service, input_pane, output_pane, _output_canvas = _build_service()
    workflow_a = WorkflowState()
    workflow_b = WorkflowState()
    input_a = uuid.uuid4()
    input_b = uuid.uuid4()
    output_a = uuid.uuid4()
    output_b = uuid.uuid4()
    workflow_a.canvas.input_image_uuid = input_a
    workflow_a.canvas.input_key_map["A:load"] = input_a
    workflow_a.output_image_uuids = [output_a]
    workflow_a.active_output_uuid = output_a
    workflow_b.canvas.input_image_uuid = input_b
    workflow_b.canvas.input_key_map["B:load"] = input_b
    workflow_b.output_image_uuids = [output_b]
    workflow_b.active_output_uuid = output_b
    input_pane.images[input_a] = ("input-a", Path("input-a.png"))
    input_pane.images[input_b] = ("input-b", Path("input-b.png"))
    output_pane.images[output_a] = ("output-a", Path("output-a.png"))
    output_pane.images[output_b] = ("output-b", Path("output-b.png"))
    _store_image_record(
        service, output_a, ImageMeta("A", "Cube", 1, "", "output-a.png")
    )
    _store_image_record(
        service, output_b, ImageMeta("B", "Cube", 1, "", "output-b.png")
    )

    service.project_workflow({"A": workflow_a, "B": workflow_b}, "A")
    service.project_workflow({"A": workflow_a, "B": workflow_b}, "B")

    assert set(input_pane.images) == {input_a, input_b}
    assert set(output_pane.images) == {output_a, output_b}
    assert input_pane.current_id == input_b
    assert output_pane.current_id == output_b


def test_project_workflow_switch_rebinds_both_canvases_to_legal_routes() -> None:
    """Tab switching should rebind Input and Output sessions to B-owned routes."""

    service, input_pane, output_pane, output_canvas = _build_service()
    workflow_a = WorkflowState()
    workflow_b = WorkflowState()
    input_a = uuid.uuid4()
    input_b = uuid.uuid4()
    output_a = uuid.uuid4()
    output_b = uuid.uuid4()
    workflow_a.canvas.input_image_uuid = input_a
    workflow_a.canvas.input_key_map["A:load"] = input_a
    workflow_a.output_image_uuids = [output_a]
    workflow_a.active_output_uuid = output_a
    workflow_b.canvas.input_image_uuid = input_b
    workflow_b.canvas.input_key_map["B:load"] = input_b
    workflow_b.output_image_uuids = [output_b]
    workflow_b.active_output_uuid = output_b
    input_pane.images[input_a] = ("input-a", Path("input-a.png"))
    input_pane.images[input_b] = ("input-b", Path("input-b.png"))
    output_pane.images[output_a] = ("output-a", Path("output-a.png"))
    output_pane.images[output_b] = ("output-b", Path("output-b.png"))
    _store_image_record(
        service,
        output_a,
        ImageMeta("A", "Save", 1, "", "output-a.png", source_key="A:save"),
    )
    _store_image_record(
        service,
        output_b,
        ImageMeta("B", "Save", 1, "", "output-b.png", source_key="B:save"),
    )
    workflows = {"A": workflow_a, "B": workflow_b}

    service.project_workflow(workflows, "A")
    output_canvas.sync_session_calls.clear()
    service.project_workflow(workflows, "B")

    input_session = service.canvas_session_boundary.current_session(CanvasKind.INPUT)
    output_session = service.canvas_session_boundary.current_session(CanvasKind.OUTPUT)
    bound_output_session = output_canvas.sync_session_calls[-1]
    assert isinstance(bound_output_session, OutputCanvasSession)
    assert input_session is not None
    assert output_session is bound_output_session.session
    assert input_session.workflow_id.value == "B"
    assert input_session.active_route.route_kind == "input_image"
    assert input_session.active_route.primary_image_id == input_b
    assert output_session.workflow_id.value == "B"
    assert output_session.active_route == bound_output_session.active_route
    assert output_session.active_route.route_key == (
        f"image:{output_b};scene:;source:B:save;set:1"
    )
    assert output_session.active_route.primary_image_id == output_b
    assert input_pane.current_id == input_b
    assert output_pane.current_id == output_b
    assert set(input_pane.images) == {input_a, input_b}
    assert set(output_pane.images) == {output_a, output_b}
    assert bound_output_session.allowed_image_ids == frozenset({output_b})
    assert bound_output_session.allowed_source_keys == frozenset({"B:save"})


def test_catalog_availability_is_not_workflow_membership() -> None:
    """Warm catalog images should not project unless workflow state owns them."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    catalog_only_id = uuid.uuid4()
    output_pane.images[catalog_only_id] = ("catalog-only", Path("warm.png"))
    _store_image_record(
        service,
        catalog_only_id,
        ImageMeta(
            "wf",
            "Cube",
            1,
            "",
            "warm.png",
        ),
    )

    service.project_workflow({"wf": WorkflowState()}, "wf")

    assert output_pane.images[catalog_only_id] == ("catalog-only", Path("warm.png"))
    assert output_canvas.sync_calls[-1].sources == ()


def test_project_workflow_binds_input_and_output_canvas_sessions() -> None:
    """Workflow projection binds shared Input and Output session identities."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    input_id = uuid.uuid4()
    output_id = uuid.uuid4()
    workflow.canvas.input_image_uuid = input_id
    workflow.canvas.input_key_map["wf:load"] = input_id
    workflow.output_image_uuids = [output_id]
    workflow.active_output_uuid = output_id
    _store_image_record(
        service,
        output_id,
        ImageMeta(
            workflow_name="wf",
            cube_name="Save",
            image_number=1,
            suffix="",
            path="E:/output.png",
            source_key="wf:save",
            node_id="save-node",
            generation_run_id="run-1",
            prompt_id="prompt-1",
            client_id="client-1",
            list_index=0,
        ),
    )

    service.project_workflow({"wf": workflow}, "wf")

    input_session = service.canvas_session_boundary.current_session(CanvasKind.INPUT)
    route_session = service.canvas_session_boundary.current_session(CanvasKind.OUTPUT)
    output_session = output_canvas.sync_session_calls[-1]
    assert input_session is not None
    assert input_session.workflow_id.value == "wf"
    assert input_session.active_route.primary_image_id == input_id
    assert input_session.active_route.route_kind == "input_image"
    assert isinstance(output_session, OutputCanvasSession)
    assert route_session == output_session.session
    assert output_session.workflow_id.value == "wf"
    assert output_session.active_route.primary_image_id == output_id
    assert output_session.active_route.route_key == (
        f"image:{output_id};scene:;source:wf:save;set:1"
    )
    assert output_session.projection is output_canvas.sync_calls[-1]
    assert output_session.allowed_image_ids == frozenset({output_id})
    assert output_session.allowed_source_keys == frozenset({"wf:save"})
    assert output_session.generation_identity is not None
    assert output_session.generation_identity.generation_run_id == "run-1"
    assert output_session.generation_identity.prompt_id == "prompt-1"
    assert output_session.generation_identity.client_id == "client-1"


@pytest.mark.parametrize(
    ("generation_run_id", "prompt_id", "client_id"),
    (
        ("", "prompt-1", "client-1"),
        ("run-1", "", "client-1"),
        ("run-1", "prompt-1", ""),
    ),
)
def test_project_workflow_does_not_bind_partial_output_generation_identity(
    generation_run_id: str,
    prompt_id: str,
    client_id: str,
) -> None:
    """Workflow projection binds Output generation identity only when complete."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    output_id = uuid.uuid4()
    workflow.output_image_uuids = [output_id]
    workflow.active_output_uuid = output_id
    _store_image_record(
        service,
        output_id,
        ImageMeta(
            workflow_name="wf",
            cube_name="Save",
            image_number=1,
            suffix="",
            path="E:/output.png",
            source_key="wf:save",
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            client_id=client_id,
        ),
    )

    service.project_workflow({"wf": workflow}, "wf")

    output_session = output_canvas.sync_session_calls[-1]
    assert isinstance(output_session, OutputCanvasSession)
    assert output_session.generation_identity is None


def test_unchanged_project_workflow_keeps_existing_session_token_current() -> None:
    """An unchanged projection should not invalidate active display authority."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    output_id = uuid.uuid4()
    workflow.output_image_uuids = [output_id]
    workflow.active_output_uuid = output_id
    _store_image_record(
        service,
        output_id,
        ImageMeta(
            "wf",
            "Save",
            1,
            "",
            "E:/output.png",
            source_key="wf:save",
        ),
    )

    service.project_workflow({"wf": workflow}, "wf")
    first_output_session = _output_canvas.sync_session_calls[-1]
    assert isinstance(first_output_session, OutputCanvasSession)

    service.project_workflow({"wf": workflow}, "wf")
    authorization = service.canvas_session_boundary.authorize_display_mutation(
        first_output_session.token(),
    )

    assert authorization.accepted is True
    assert authorization.rejection_reason is None


def test_project_workflow_clears_foreign_output_image_when_switching_to_grid() -> None:
    """Inactive Output images stay cached but must not stay visible."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow_a = WorkflowState()
    workflow_b = WorkflowState()
    output_a = uuid.uuid4()
    output_b1 = uuid.uuid4()
    output_b2 = uuid.uuid4()
    workflow_a.output_image_uuids = [output_a]
    workflow_a.active_output_uuid = output_a
    workflow_b.output_image_uuids = [output_b1, output_b2]
    workflow_b.active_output_uuid = None
    output_pane.images[output_a] = ("output-a", Path("output-a.png"))
    output_pane.images[output_b1] = ("output-b1", Path("output-b1.png"))
    output_pane.images[output_b2] = ("output-b2", Path("output-b2.png"))
    _store_image_record(
        service,
        output_a,
        ImageMeta(
            "A",
            "Cube",
            1,
            "",
            "output-a.png",
            source_key="A:save",
        ),
    )
    _store_image_record(
        service,
        output_b1,
        ImageMeta(
            "B",
            "Cube",
            1,
            "",
            "output-b1.png",
            source_key="B:save",
        ),
    )
    _store_image_record(
        service,
        output_b2,
        ImageMeta(
            "B",
            "Cube",
            2,
            "",
            "output-b2.png",
            source_key="B:save",
        ),
    )

    service.project_workflow({"A": workflow_a, "B": workflow_b}, "A")
    service.project_workflow({"A": workflow_a, "B": workflow_b}, "B")

    assert set(output_pane.images) == {output_a, output_b1, output_b2}
    assert output_pane.selection_calls[-1] is None
    assert output_pane.current_id is None
    assert output_canvas.sync_calls[-1].active_uuid is None
    assert output_canvas.sync_calls[-1].active_set_index == 0


def test_set_active_input_image_rejects_uuid_not_owned_by_active_workflow() -> None:
    """Input route activation rejects non-owned image UUIDs."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    owned_image = uuid.uuid4()
    foreign_image = uuid.uuid4()
    input_pane.current_id = owned_image

    workflow = WorkflowState()
    workflow.canvas.input_key_map["Cube:Image"] = owned_image
    workflow.canvas.input_image_uuid = owned_image

    input_service.set_active_input_image("wf", workflow, foreign_image)

    assert input_pane.selection_calls == []
    assert input_pane.current_id == owned_image


def test_project_workflow_rejects_stale_active_input_image_not_in_workflow_state() -> (
    None
):
    """Input projection should not treat cached or active QPane images as membership."""

    service, _input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    stale_image = uuid.uuid4()
    stale_mask = uuid.uuid4()
    input_pane.images[stale_image] = ("cached", Path("cached.png"))
    input_pane.current_id = stale_image
    workflow = WorkflowState()
    workflow.canvas.input_image_uuid = stale_image
    workflow.canvas.active_input_mask_uuid = stale_mask
    workflow.canvas.mask_associations[("Cube", "Mask")] = stale_mask
    workflow.canvas.mask_to_image_map[stale_mask] = stale_image

    service.project_workflow({"wf": workflow}, "wf")

    assert workflow.canvas.input_image_uuid is None
    assert workflow.canvas.active_input_mask_uuid is None
    assert input_pane.current_id is None
    assert input_pane.active_mask is None
    assert input_pane.selection_calls[-1] is None


def test_set_active_workflow_mask_rejects_mask_for_different_input_image() -> None:
    """Phase 0 - Input mask activation rejects masks outside the active image."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    active_image = uuid.uuid4()
    foreign_image = uuid.uuid4()
    foreign_mask = uuid.uuid4()
    workflow.canvas.input_image_uuid = active_image
    workflow.canvas.mask_associations[("Cube", "Mask")] = foreign_mask
    workflow.canvas.mask_to_image_map[foreign_mask] = foreign_image

    input_service.set_active_workflow_mask("wf", workflow, foreign_mask)

    assert workflow.canvas.active_input_mask_uuid is None
    assert input_pane.active_mask is None


def test_project_workflow_hydrates_output_canvas_from_image_registry() -> None:
    """Projection should hydrate visible output caches from registry records."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    image = object()
    meta = ImageMeta("wf", "Cube", 1, "", "", source_key="wf:cube")
    workflow.output_image_uuids.append(image_id)
    _store_image_record(service, image_id, meta, payload=image)

    service.project_workflow({"wf": workflow}, "wf")

    workflow_id, image_ids = output_canvas.prepare_calls[-1]
    assert workflow_id == "wf"
    assert image_ids == (image_id,)
    assert service.image_registry.payload_for(image_id) is image
    assert service.image_registry.metadata_for(image_id) is meta
    assert output_canvas.sync_calls[-1].sources


def test_project_workflow_warms_all_scene_overview_images() -> None:
    """Scene overview projection should warm every scene representative image."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    workflow.output_image_uuids = list(image_ids)
    workflow.active_output_scene_overview = True
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    payloads = {image_id: object() for image_id in image_ids}
    for index, image_id in enumerate(image_ids):
        _store_image_record(
            service,
            image_id,
            ImageMeta(
                "Scene Test",
                "Text",
                1,
                "",
                f"E:/outputs/scene-{index}.png",
                source_key="wf:text",
                source_label="Text",
                scene_run_id="scene-run",
                scene_key=f"scene-{index}",
                scene_title=f"Scene {index}",
                scene_order=index,
                scene_count=len(image_ids),
                list_index=0,
                generation_run_id="run",
                prompt_id="prompt",
                client_id="client",
                node_id="node",
            ),
            payload=payloads[image_id],
        )

    service.project_workflow({"wf": workflow}, "wf")

    warmed_ids = tuple(image_id for image_id, _image, _path in output_pane.add_calls)
    assert set(warmed_ids) == set(image_ids)
    assert len(warmed_ids) == len(image_ids)
    assert set(output_pane.images) == set(image_ids)
    assert output_canvas.sync_calls[-1].active_scene_overview is True
    assert [
        scene.primary_image_id for scene in output_canvas.sync_calls[-1].scene_groups
    ] == image_ids


def test_project_workflow_clears_transient_previews_when_workflow_changes() -> None:
    """Application session transition should retire previews before binding output."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow_a = WorkflowState()
    workflow_b = WorkflowState()
    image_a = uuid.uuid4()
    image_b = uuid.uuid4()
    payload_a = object()
    payload_b = object()
    meta_a = ImageMeta("wf-a", "Cube", 1, "", "", source_key="A:cube")
    meta_b = ImageMeta("wf-b", "Cube", 1, "", "", source_key="B:cube")
    workflow_a.output_image_uuids.append(image_a)
    workflow_b.output_image_uuids.append(image_b)
    _store_image_record(service, image_a, meta_a, payload=payload_a)
    _store_image_record(service, image_b, meta_b, payload=payload_b)

    service.project_workflow({"A": workflow_a, "B": workflow_b}, "A")
    output_canvas.events.clear()

    service.project_workflow({"A": workflow_a, "B": workflow_b}, "B")

    assert output_canvas.clear_preview_calls == [None, None]
    assert output_canvas.events[0] == ("clear_previews", None)
    assert output_canvas.events[1] == ("bind", "B")
    assert output_canvas.prepare_calls[-1][1] == (image_b,)
    assert service.image_registry.payload_for(image_b) is payload_b


def test_project_workflow_keeps_transient_previews_when_reprojecting_same_workflow() -> (
    None
):
    """Same-workflow duplicate projection must not replay stale visible routes."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    payload = object()
    meta = ImageMeta("wf", "Cube", 1, "", "", source_key="wf:cube")
    workflow.output_image_uuids.append(image_id)
    _store_image_record(service, image_id, meta, payload=payload)

    service.project_workflow({"wf": workflow}, "wf")
    output_canvas.clear_preview_calls.clear()
    output_canvas.events.clear()
    output_canvas.prepare_calls.clear()
    output_canvas.sync_calls.clear()

    service.project_workflow({"wf": workflow}, "wf")

    assert output_canvas.clear_preview_calls == []
    assert output_canvas.events == []
    assert output_canvas.prepare_calls == []
    assert output_canvas.sync_calls == []


def test_project_workflow_resyncs_same_workflow_after_metadata_changes() -> None:
    """Same-workflow projection should resync when display metadata changes."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    payload = object()
    meta = ImageMeta("wf", "Cube", 1, "", "", source_key="wf:cube")
    workflow.output_image_uuids.append(image_id)
    _store_image_record(service, image_id, meta, payload=payload)

    service.project_workflow({"wf": workflow}, "wf")
    output_canvas.events.clear()
    output_canvas.prepare_calls.clear()
    output_canvas.sync_calls.clear()

    meta.cube_execution_duration_ms = 42.5
    service.project_workflow({"wf": workflow}, "wf")

    assert output_canvas.events[0] == ("bind", "wf")
    assert output_canvas.prepare_calls[-1][1] == (image_id,)
    assert service.image_registry.payload_for(image_id) is payload
    assert output_canvas.sync_calls


def test_add_output_image_keeps_multi_scene_automatic_projection_on_all() -> None:
    """Scene outputs from the same source should not auto-open the last scene grid."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    workflows = {"wf": workflow}

    _add_output_image(
        service,
        workflows,
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=object(),
        image_meta=ImageMeta(
            workflow_name="Recipe",
            cube_name="Text",
            image_number=1,
            suffix="",
            path="E:/outputs/portrait.png",
            source_key="wf:text",
            source_label="Text",
            scene_run_id="run-1",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
    )
    _add_output_image(
        service,
        workflows,
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=object(),
        image_meta=ImageMeta(
            workflow_name="Recipe",
            cube_name="Text",
            image_number=1,
            suffix="",
            path="E:/outputs/cafe.png",
            source_key="wf:text",
            source_label="Text",
            scene_run_id="run-1",
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
            scene_count=2,
        ),
    )

    first_projection = output_canvas.sync_calls[-2]
    final_projection = output_canvas.sync_calls[-1]

    assert first_projection.active_scene_overview is True
    assert first_projection.scene_count == 2
    assert final_projection.active_scene_overview is True
    assert final_projection.scene_count == 2
    assert final_projection.active_set_index == 1
    assert final_projection.active_uuid is None
    assert workflow.active_output_uuid is None
    assert workflow.active_output_source_key is None
    assert workflow.active_output_scene_key is None
    assert workflow.active_output_scene_overview is True


def test_begin_output_generation_clears_stale_manual_focus_for_scene_run() -> None:
    """A new multi-scene run should start from automatic scene overview intent."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    selected_id = uuid.uuid4()
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_uuid = selected_id
    workflow.active_output_source_key = "wf:old"
    workflow.active_output_set_index = 1
    workflow.active_output_scene_key = "old-scene"
    workflow.active_output_scene_overview = False

    service.output_canvas_state_service.begin_output_generation(
        {"wf": workflow},
        "wf",
        scene_run_id="run-2",
        scene_count=2,
    )

    assert workflow.output_focus_mode is OutputFocusMode.AUTOMATIC
    assert workflow.active_output_uuid is None
    assert workflow.active_output_source_key is None
    assert workflow.active_output_set_index == 1
    assert workflow.active_output_scene_key is None
    assert workflow.active_output_scene_overview is True


def test_project_workflow_does_not_deselect_legacy_output_for_scene_overview() -> None:
    """Scene overview projection should let OutputCanvas own the visible target."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    workflows = {"wf": workflow}

    _add_output_image(
        service,
        workflows,
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=object(),
        image_meta=ImageMeta(
            workflow_name="Recipe",
            cube_name="Text",
            image_number=1,
            suffix="",
            path="E:/outputs/portrait.png",
            source_key="wf:text",
            source_label="Text",
            scene_run_id="run-1",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
    )

    assert output_canvas.sync_calls[-1].active_scene_overview is True
    assert None not in output_pane.selection_calls


def test_add_output_image_records_automatic_follow_fields() -> None:
    """Automatic output arrival should update follow fields without manual mode."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()

    _add_output_image(
        service,
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=object(),
        image_meta=ImageMeta(
            "wf",
            "Cube",
            1,
            "",
            "E:/out.png",
            source_key="wf:node",
        ),
    )

    assert workflow.output_focus_mode is OutputFocusMode.AUTOMATIC
    assert workflow.active_output_uuid == workflow.output_image_uuids[-1]
    assert workflow.active_output_source_key == "wf:node"
    assert workflow.active_output_set_index == 1


def test_register_output_image_does_not_touch_pane_or_projection() -> None:
    """Output registration should update state without mutating visible widgets."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image = object()
    image_meta = ImageMeta(
        "wf",
        "Cube",
        1,
        "",
        "E:/out.png",
        source_key="wf:node",
    )

    result = service.output_canvas_state_service.register_output_image(
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=image,
        image_meta=image_meta,
    )

    assert result.image_id in workflow.output_image_uuids
    assert service.image_registry.payload_for(result.image_id) is image
    assert service.image_registry.metadata_for(result.image_id) == image_meta
    assert output_pane.images == {}
    assert output_canvas.register_calls == []
    assert output_canvas.sync_calls == []


def test_inactive_output_registration_updates_only_target_workflow_state() -> None:
    """Inactive final output arrival should not mutate the visible workflow or pane."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    active_workflow = WorkflowState()
    inactive_workflow = WorkflowState()
    image = object()
    image_meta = ImageMeta(
        "Inactive",
        "Cube",
        1,
        "",
        "E:/inactive.png",
        source_key="wf-b:node",
    )

    result = service.output_canvas_state_service.register_output_image(
        {"wf-a": active_workflow, "wf-b": inactive_workflow},
        origin_workflow_id="wf-b",
        active_workflow_id="wf-a",
        image=image,
        image_meta=image_meta,
    )

    assert result.projection_intent.should_schedule is False
    assert result.image_id in inactive_workflow.output_image_uuids
    assert active_workflow.output_image_uuids == []
    assert active_workflow.active_output_uuid is None
    assert service.image_registry.payload_for(result.image_id) is image
    assert service.image_registry.metadata_for(result.image_id) == image_meta
    assert output_pane.images == {}
    assert output_canvas.sync_calls == []


def test_inactive_prepared_output_commit_preserves_visible_qpane_route() -> None:
    """Inactive final output commits should not schedule or apply visible routes."""

    _app()
    service, _input_pane, output_pane, output_canvas = _build_service()
    active_workflow = WorkflowState()
    inactive_workflow = WorkflowState()
    workflows = {"wf-a": active_workflow, "wf-b": inactive_workflow}
    active_image = object()
    inactive_image = object()
    active_meta = ImageMeta(
        "Active",
        "Active Cube",
        1,
        "",
        "E:/active.png",
        source_key="wf-a:node",
    )
    inactive_meta = ImageMeta(
        "Inactive",
        "Inactive Cube",
        1,
        "",
        "E:/inactive.png",
        source_key="wf-b:node",
    )
    active_result = service.output_canvas_state_service.register_output_image(
        workflows,
        origin_workflow_id="wf-a",
        active_workflow_id="wf-a",
        image=active_image,
        image_meta=active_meta,
    )
    service.project_output(
        workflows,
        "wf-a",
        registered_image_id=active_result.image_id,
    )
    visible_image_id = output_pane.current_id
    output_canvas.sync_calls.clear()
    output_pane.selection_calls.clear()
    scheduled_projection_calls: list[tuple[str, uuid.UUID | None]] = []

    def project_workflow(
        workflow_id: str,
        registered_image_id: uuid.UUID | None = None,
    ) -> None:
        scheduled_projection_calls.append((workflow_id, registered_image_id))
        service.project_output(
            workflows,
            workflow_id,
            registered_image_id=registered_image_id,
        )

    scheduler = CanvasProjectionScheduler(
        project_workflow=project_workflow,
        active_workflow_id=lambda: "wf-a",
        output_canvas_visible=lambda: True,
    )

    def commit_prepared(_prepared: PreparedOutputImage):
        return service.output_canvas_state_service.register_output_image(
            workflows,
            origin_workflow_id="wf-b",
            active_workflow_id="wf-a",
            image=inactive_image,
            image_meta=inactive_meta,
        )

    queue = PreparedOutputCommitQueue(
        commit_prepared=commit_prepared,
        handle_failure=lambda _failure: None,
        projection_scheduler=scheduler,
        output_activity_marker=lambda _reason: None,
    )
    queue.enqueue_prepared(
        PreparedOutputImage(
            request=OutputImageCommitRequest(
                workflow_id="wf-b",
                file_path=Path("E:/inactive.png"),
                node_id="node",
                node_meta_title="Inactive.Output",
                workflow_name="Inactive",
                source_key="wf-b:node",
                source_label="Inactive Cube",
            ),
            image=QImage(8, 8, QImage.Format.Format_ARGB32),
        )
    )

    queue.drain_once()

    assert inactive_workflow.output_image_uuids
    assert active_workflow.output_image_uuids == [visible_image_id]
    assert output_pane.current_id == visible_image_id
    assert output_pane.selection_calls == []
    assert output_canvas.sync_calls == []
    assert scheduled_projection_calls == []
    assert output_pane.images == {
        visible_image_id: (active_image, Path("E:/active.png"))
    }


def test_register_generated_output_rejects_missing_workflow(caplog) -> None:
    """Strict live registration should reject missing workflow identity."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    image = object()
    image_meta = ImageMeta(
        "wf",
        "Cube",
        1,
        "",
        "E:/out.png",
        source_key="wf:node",
        source_label="Cube",
        node_id="node",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        list_index=0,
        batch_index=0,
        width=640,
        height=480,
    )
    caplog.set_level(
        "WARNING",
        logger="sugarsubstitute.application.workflows.output_canvas_state_service",
    )

    result = service.output_canvas_state_service.register_generated_output(
        {},
        active_workflow_id="wf",
        event=_live_final_event(),
        image=image,
        image_meta=image_meta,
    )

    assert result.workflow_id == "wf"
    assert result.projection_intent.should_schedule is False
    assert result.active_output_changed is False
    assert result.image_id is None
    assert "missing_workflow" in caplog.text
    assert "source_key=wf:node" in caplog.text


def test_register_generated_output_rejects_metadata_identity_mismatch(caplog) -> None:
    """Strict live registration should fail closed on metadata identity drift."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    image_meta = ImageMeta(
        "wf",
        "Cube",
        1,
        "",
        "E:/out.png",
        source_key="wf:node",
        source_label="Cube",
        node_id="node",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        list_index=2,
        width=640,
        height=480,
    )
    caplog.set_level(
        "WARNING",
        logger="sugarsubstitute.application.workflows.output_canvas_state_service",
    )

    result = service.output_canvas_state_service.register_generated_output(
        {"wf": workflow},
        active_workflow_id="wf",
        event=_live_final_event(),
        image=object(),
        image_meta=image_meta,
    )

    assert result.workflow_id == "wf"
    assert result.projection_intent.should_schedule is False
    assert result.active_output_changed is False
    assert workflow.output_image_uuids == []
    assert "list_index_mismatch" in caplog.text


def test_register_generated_output_rejects_dimension_or_scene_drift(caplog) -> None:
    """Strict live registration should verify dimensions and scene identity."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    event = LiveFinalOutputEvent(
        identity=OutputVisualIdentity(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            source_key="wf:node",
            source_label="Cube",
            scene=SourceOnlyOutputIdentity(),
        ),
        node_id="node",
        workflow_payload={"node": {"class_type": "SugarCubes.CubeOutput"}},
        file_path=Path("E:/out.png"),
        position=OutputResultPosition(list_index=0, batch_index=0),
        artifact_width=640,
        artifact_height=480,
    )
    image_meta = ImageMeta(
        "wf",
        "Cube",
        1,
        "",
        "E:/out.png",
        source_key="wf:node",
        source_label="Cube",
        node_id="node",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        list_index=0,
        width=639,
        height=480,
    )
    caplog.set_level(
        "WARNING",
        logger="sugarsubstitute.application.workflows.output_canvas_state_service",
    )

    result = service.output_canvas_state_service.register_generated_output(
        {"wf": workflow},
        active_workflow_id="wf",
        event=event,
        image=object(),
        image_meta=image_meta,
    )

    assert result.registered is False
    assert workflow.output_image_uuids == []
    assert result.image_id is None
    assert "artifact_width_mismatch" in caplog.text


def test_register_output_image_does_not_warm_visible_pane() -> None:
    """Final output registration should leave visible QPane routes untouched."""

    service, _input_pane, output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    image = object()
    image_meta = ImageMeta("wf", "Cube", 1, "", "E:/out.png")
    result = service.output_canvas_state_service.register_output_image(
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=image,
        image_meta=image_meta,
    )

    assert result.image_id is not None
    assert output_pane.add_calls == []
    assert output_pane.current_id is None


def test_project_output_warms_output_catalog_and_syncs() -> None:
    """Scheduled projection should cache projected images before route application."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image = object()
    image_meta = ImageMeta(
        "wf",
        "Cube",
        1,
        "",
        "E:/out.png",
        source_key="wf:node",
    )
    result = service.output_canvas_state_service.register_output_image(
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=image,
        image_meta=image_meta,
    )

    service.project_output(
        {"wf": workflow},
        "wf",
        registered_image_id=result.image_id,
    )

    assert output_canvas.register_calls == []
    assert output_canvas.sync_calls
    assert output_pane.add_calls == [(result.image_id, image, Path("E:/out.png"))]
    assert output_pane.current_id == result.image_id


def test_repeated_output_projection_skips_existing_identical_payload() -> None:
    """Projection catalog warming should not re-add unchanged output payloads."""

    service, _input_pane, output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    image = object()
    image_meta = ImageMeta("wf", "Cube", 1, "", "E:/out.png")
    result = service.output_canvas_state_service.register_output_image(
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=image,
        image_meta=image_meta,
    )

    service.project_output({"wf": workflow}, "wf")
    service.project_output({"wf": workflow}, "wf")

    assert output_pane.add_calls == [(result.image_id, image, Path("E:/out.png"))]


def test_repeated_output_projection_does_not_reapply_visible_route() -> None:
    """Unchanged Output projection must not replay stale visible routes."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image = object()
    image_meta = ImageMeta("wf", "Cube", 1, "", "E:/out.png", source_key="wf:cube")
    service.output_canvas_state_service.register_output_image(
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=image,
        image_meta=image_meta,
    )

    service.project_output({"wf": workflow}, "wf")
    first_session = output_canvas.sync_session_calls[-1]
    output_canvas.sync_session_calls.clear()
    output_canvas.prepare_calls.clear()
    service.project_output({"wf": workflow}, "wf")
    second_session = service.canvas_session_boundary.current_session(CanvasKind.OUTPUT)

    assert output_canvas.sync_session_calls == []
    assert output_canvas.prepare_calls == []
    assert second_session is not None
    assert second_session.revision.value == first_session.revision.value


def test_add_output_image_does_not_overwrite_manual_focus() -> None:
    """Manual output focus should stay sticky when later outputs arrive."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    selected_id = uuid.uuid4()
    workflow.output_image_uuids = [selected_id]
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_uuid = selected_id
    workflow.active_output_set_index = 1
    workflow.active_output_source_key = "wf:node"
    _store_image_record(
        service,
        selected_id,
        ImageMeta(
            "wf",
            "Cube",
            1,
            "",
            "E:/one.png",
            source_key="wf:node",
        ),
    )

    _add_output_image(
        service,
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=object(),
        image_meta=ImageMeta(
            "wf",
            "Cube",
            2,
            "",
            "E:/two.png",
            source_key="wf:node",
        ),
    )

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid == selected_id
    assert workflow.active_output_set_index == 1
    assert workflow.active_output_source_key == "wf:node"


def test_clear_images_for_closed_workflow_keeps_shared_references() -> None:
    """Closing a workflow removes only UUIDs no longer referenced by others."""
    service, input_service, input_pane, output_pane, _output_canvas = _build_services()
    wf_closed = WorkflowState()
    wf_remaining = WorkflowState()

    shared_id = uuid.uuid4()
    closed_only_id = uuid.uuid4()

    wf_closed.canvas.input_key_map["A:img"] = closed_only_id
    wf_closed.output_image_uuids = [shared_id]
    wf_remaining.output_image_uuids = [shared_id]

    input_pane.images[closed_only_id] = ("img", None)
    output_pane.images[shared_id] = ("out", None)
    _store_image_record(service, shared_id, ImageMeta("wf", "cube", 1, "", ""))
    _store_image_record(service, closed_only_id, ImageMeta("wf", "cube", 1, "", ""))

    input_service.prune_closed_workflow_images(
        wf_closed,
        {"remaining": wf_remaining},
    )
    service.prune_closed_workflow_images(
        "closed",
        wf_closed,
        {"remaining": wf_remaining},
    )

    assert closed_only_id not in input_pane.images
    assert service.image_registry.metadata_for(closed_only_id) is None
    assert shared_id in output_pane.images
    assert service.image_registry.metadata_for(shared_id) is not None


def test_load_mask_from_file_links_mask_to_explicit_image() -> None:
    """Loading mask from file stores association against the explicit target image."""
    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    association_key = ("AliasA", "MaskNode")
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    input_pane.next_loaded_mask_id = mask_id
    workflow.canvas.input_key_map["AliasA:ImageNode"] = image_id
    workflow.canvas.input_image_uuid = image_id

    loaded = input_service.load_mask_from_file(
        "wf",
        workflow,
        association_key,
        image_id,
        Path("mask.png"),
    )

    assert loaded == mask_id
    assert input_pane.current_id == image_id
    assert workflow.canvas.mask_associations[association_key] == mask_id
    assert workflow.canvas.mask_to_image_map[mask_id] == image_id


def test_restore_input_mask_remaps_snapshot_id_and_records_active_mask() -> None:
    """Restored masks should replace saved ids with live QPane mask ids."""
    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    association_key = ("AliasA", "MaskNode")
    image_id = uuid.uuid4()
    snapshot_mask_id = uuid.uuid4()
    live_mask_id = uuid.uuid4()
    input_pane.next_loaded_mask_id = live_mask_id
    workflow.canvas.input_key_map["AliasA:ImageNode"] = image_id
    workflow.canvas.input_image_uuid = image_id
    workflow.canvas.mask_associations[association_key] = snapshot_mask_id
    workflow.canvas.mask_to_image_map[snapshot_mask_id] = image_id
    workflow.canvas.active_input_mask_uuid = snapshot_mask_id

    restored = input_service.restore_input_mask(
        "wf",
        workflow,
        snapshot_mask_id=snapshot_mask_id,
        image_id=image_id,
        path=Path("mask.png"),
        association_key=association_key,
    )

    assert restored == live_mask_id
    assert input_pane.current_id == image_id
    assert workflow.canvas.mask_associations[association_key] == live_mask_id
    assert workflow.canvas.mask_to_image_map[live_mask_id] == image_id
    assert snapshot_mask_id not in workflow.canvas.mask_to_image_map
    assert workflow.canvas.active_input_mask_uuid == live_mask_id


def test_project_workflow_restores_active_input_mask() -> None:
    """Workflow projection should restore the selected input mask for its image."""
    service, input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    workflow.canvas.input_image_uuid = image_id
    workflow.canvas.input_key_map["AliasA:ImageNode"] = image_id
    workflow.canvas.mask_associations[("AliasA", "MaskNode")] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = image_id
    workflow.canvas.active_input_mask_uuid = mask_id

    service.project_workflow({"wf": workflow}, "wf")

    assert input_pane.current_id == image_id
    assert input_pane.active_mask == mask_id


def test_drop_mask_association_removes_workflow_state_and_pane_layer() -> None:
    """Dropping a stale mask association should remove its pane layer."""
    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    association_key = ("AliasA", "MaskNode")
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    workflow.canvas.mask_associations[association_key] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = image_id

    input_service.drop_mask_association(workflow, association_key)

    assert association_key not in workflow.canvas.mask_associations
    assert mask_id not in workflow.canvas.mask_to_image_map
    assert input_pane.removed_masks == [(image_id, mask_id)]


def test_drop_mask_association_preserves_shared_pane_layer() -> None:
    """A still-referenced mask layer should stay attached to the pane."""
    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    workflow.canvas.mask_associations[("AliasA", "MaskNodeA")] = mask_id
    workflow.canvas.mask_associations[("AliasA", "MaskNodeB")] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = image_id

    input_service.drop_mask_association(workflow, ("AliasA", "MaskNodeA"))

    assert ("AliasA", "MaskNodeA") not in workflow.canvas.mask_associations
    assert workflow.canvas.mask_associations[("AliasA", "MaskNodeB")] == mask_id
    assert workflow.canvas.mask_to_image_map[mask_id] == image_id
    assert input_pane.removed_masks == []


def test_update_mask_from_file_rejects_mask_for_different_input_image() -> None:
    """Mask pixel updates should require mask-to-image ownership proof."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    foreign_image = uuid.uuid4()
    mask_id = uuid.uuid4()
    workflow.canvas.input_key_map["Cube:Image"] = image_id
    workflow.canvas.mask_associations[("Cube", "Mask")] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = foreign_image

    updated = input_service.update_mask_from_file(
        "wf",
        workflow,
        ("Cube", "Mask"),
        image_id,
        mask_id,
        Path("mask.png"),
        (640, 480),
        (640, 480),
    )

    assert updated is False
    assert input_pane.updated_masks == []


def test_update_mask_from_file_updates_authorized_associated_mask() -> None:
    """Authorized mask pixel updates should route through the Input state service."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    workflow.canvas.input_key_map["Cube:Image"] = image_id
    workflow.canvas.mask_associations[("Cube", "Mask")] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = image_id

    updated = input_service.update_mask_from_file(
        "wf",
        workflow,
        ("Cube", "Mask"),
        image_id,
        mask_id,
        Path("mask.png"),
        (640, 480),
        (640, 480),
    )

    assert updated is True
    assert input_pane.selection_calls == [image_id]
    assert input_pane.updated_masks == [(mask_id, "mask.png")]


def test_update_mask_from_file_rejects_unverified_dimensions() -> None:
    """Mask pixel updates should fail closed when dimensions are unavailable."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    workflow.canvas.input_key_map["Cube:Image"] = image_id
    workflow.canvas.mask_associations[("Cube", "Mask")] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = image_id

    updated = input_service.update_mask_from_file(
        "wf",
        workflow,
        ("Cube", "Mask"),
        image_id,
        mask_id,
        Path("mask.png"),
        (640, 480),
        None,
    )

    assert updated is False
    assert input_pane.selection_calls == []
    assert input_pane.updated_masks == []


def test_update_mask_from_file_rejects_dimension_mismatch() -> None:
    """Mask pixel updates should require selected mask dimensions to match."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    workflow.canvas.input_key_map["Cube:Image"] = image_id
    workflow.canvas.mask_associations[("Cube", "Mask")] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = image_id

    updated = input_service.update_mask_from_file(
        "wf",
        workflow,
        ("Cube", "Mask"),
        image_id,
        mask_id,
        Path("mask.png"),
        (640, 480),
        (320, 240),
    )

    assert updated is False
    assert input_pane.selection_calls == []
    assert input_pane.updated_masks == []


def test_clear_output_for_workflow_deselects_canvas_and_removes_unreferenced_images() -> (
    None
):
    """Clearing workflow output should deselect output UI and remove orphaned UUIDs."""
    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    out_a = uuid.uuid4()
    out_b = uuid.uuid4()
    workflow.output_image_uuids = [out_a, out_b]
    workflow.active_output_uuid = out_b
    output_pane.images[out_a] = ("img-a", None)
    output_pane.images[out_b] = ("img-b", None)
    output_pane.current_id = out_b
    _store_image_record(service, out_a, ImageMeta("wf", "cube", 1, "", ""))
    _store_image_record(service, out_b, ImageMeta("wf", "cube", 2, "", ""))
    service.project_output({"wf": workflow}, "wf")
    output_pane.selection_calls.clear()
    output_canvas.clear_preview_calls.clear()
    output_canvas.sync_calls.clear()

    service.clear_output_for_workflow({"wf": workflow}, "wf")

    assert workflow.output_image_uuids == []
    assert workflow.active_output_uuid is None
    assert workflow.output_focus_mode is OutputFocusMode.AUTOMATIC
    assert workflow.active_output_set_index == 1
    assert workflow.active_output_source_key is None
    assert output_pane.selection_calls == [None]
    assert output_pane.current_id is None
    assert output_canvas.clear_preview_calls == [None]
    assert output_canvas.sync_calls[-1].sources == ()
    assert out_a not in output_pane.images
    assert out_b not in output_pane.images
    assert service.image_registry.metadata_for(out_a) is None
    assert service.image_registry.metadata_for(out_b) is None


def test_clear_inactive_output_for_workflow_does_not_clear_visible_route() -> None:
    """Clearing inactive workflow output should not mutate active Output UI."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    active_workflow = WorkflowState()
    inactive_workflow = WorkflowState()
    active_id = uuid.uuid4()
    inactive_id = uuid.uuid4()
    active_workflow.output_image_uuids = [active_id]
    active_workflow.active_output_uuid = active_id
    inactive_workflow.output_image_uuids = [inactive_id]
    inactive_workflow.active_output_uuid = inactive_id
    output_pane.images[active_id] = ("active", None)
    output_pane.images[inactive_id] = ("inactive", None)
    _store_image_record(service, active_id, ImageMeta("active", "cube", 1, "", ""))
    _store_image_record(service, inactive_id, ImageMeta("inactive", "cube", 1, "", ""))
    service.project_output(
        {"active": active_workflow, "inactive": inactive_workflow}, "active"
    )
    output_pane.selection_calls.clear()
    output_canvas.clear_preview_calls.clear()
    output_canvas.sync_calls.clear()

    service.clear_output_for_workflow(
        {"active": active_workflow, "inactive": inactive_workflow},
        "inactive",
    )

    assert inactive_workflow.output_image_uuids == []
    assert inactive_workflow.active_output_uuid is None
    assert output_pane.current_id == active_id
    assert output_pane.selection_calls == []
    assert output_canvas.clear_preview_calls == []
    assert output_canvas.sync_calls == []
    assert active_id in output_pane.images
    assert inactive_id not in output_pane.images


def test_update_canvases_automatic_batch_uses_grid_and_keeps_link_group() -> None:
    """Automatic multi-output source should select grid while linking outputs."""
    service, input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    workflow.canvas.input_image_uuid = uuid.uuid4()
    output_a = uuid.uuid4()
    output_b = uuid.uuid4()
    workflow.output_image_uuids = [output_a, output_b]
    workflow.active_output_uuid = None
    _store_image_record(service, output_a, ImageMeta("wf", "cube", 1, "", ""))
    _store_image_record(service, output_b, ImageMeta("wf", "cube", 2, "", ""))

    service.project_workflow({"wf": workflow}, "wf")

    assert input_pane.current_id == workflow.canvas.input_image_uuid
    assert output_pane.current_id is None
    assert workflow.active_output_uuid is None
    assert workflow.active_output_set_index == 0
    assert len(output_pane.linked_groups) == 1
    assert set(output_pane.linked_groups[0].members) == {output_a, output_b}
    projection = output_canvas.sync_calls[-1]
    projected_ids = {
        item.image_id
        for source in projection.sources
        for item in source.images_by_set.values()
    }
    assert projected_ids == {output_a, output_b}
    assert projection.active_uuid is None
    assert projection.active_set_index == 0


def test_output_projection_uses_backend_list_index_not_arrival_order() -> None:
    """Out-of-order finals project into backend-defined set slots."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    late_slot = uuid.uuid4()
    first_slot = uuid.uuid4()
    workflow.output_image_uuids = [late_slot, first_slot]
    late_meta = ImageMeta(
        "wf",
        "Cube",
        1,
        "",
        "late.png",
        source_key="wf:save",
        list_index=3,
    )
    first_meta = ImageMeta(
        "wf",
        "Cube",
        2,
        "",
        "first.png",
        source_key="wf:save",
        list_index=0,
    )
    _store_image_record(service, late_slot, late_meta)
    _store_image_record(service, first_slot, first_meta)

    service.project_workflow({"wf": workflow}, "wf")

    source = output_canvas.sync_calls[-1].sources[0]
    assert source.images_by_set[1].image_id == first_slot
    assert source.images_by_set[4].image_id == late_slot


def test_update_canvases_single_output_does_not_create_link_group() -> None:
    """One output image should not create a QPane linked group."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    output_id = uuid.uuid4()
    workflow.output_image_uuids = [output_id]
    workflow.active_output_uuid = output_id
    _store_image_record(service, output_id, ImageMeta("wf", "cube", 1, "", ""))

    service.project_workflow({"wf": workflow}, "wf")

    assert output_pane.current_id == output_id
    assert output_pane.linked_groups == ()
    projection = output_canvas.sync_calls[-1]
    assert projection.sources[0].images_by_set[1].image_id == output_id
    assert projection.active_uuid == output_id


def test_project_workflow_links_only_projected_output_images() -> None:
    """Linked groups should use projection-backed images, not raw workflow membership."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    projected_a = uuid.uuid4()
    projected_b = uuid.uuid4()
    unprojected = uuid.uuid4()
    workflow.output_image_uuids = [projected_a, unprojected, projected_b]
    _store_image_record(
        service,
        projected_a,
        ImageMeta("wf", "Cube", 1, "", "E:/a.png", source_key="wf:node"),
    )
    _store_image_record(
        service,
        projected_b,
        ImageMeta("wf", "Cube", 2, "", "E:/b.png", source_key="wf:node"),
    )

    service.project_workflow({"wf": workflow}, "wf")

    assert len(output_pane.linked_groups) == 1
    assert output_pane.linked_groups[0].members == (projected_a, projected_b)
    projected_ids = {
        item.image_id
        for source in output_canvas.sync_calls[-1].sources
        for item in source.images_by_set.values()
    }
    assert projected_ids == {projected_a, projected_b}
    assert unprojected not in projected_ids


def test_project_workflow_skips_reselecting_current_output_uuid() -> None:
    """Projection should not restart QPane navigation for the current output UUID."""

    service, _input_pane, output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    output_id = uuid.uuid4()
    workflow.output_image_uuids = [output_id]
    workflow.active_output_uuid = output_id
    output_pane.current_id = output_id
    _store_image_record(service, output_id, ImageMeta("wf", "cube", 1, "", ""))

    service.project_workflow({"wf": workflow}, "wf")

    assert output_pane.selection_calls == []
    assert output_pane.current_id == output_id


def test_set_active_output_uuid_records_manual_source_and_set() -> None:
    """Concrete output selection should store manual source and set intent."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    workflow.output_image_uuids = [first_id, second_id]
    _store_image_record(
        service,
        first_id,
        ImageMeta(
            "wf",
            "Cube",
            1,
            "",
            "E:/one.png",
            source_key="wf:node",
        ),
    )
    _store_image_record(
        service,
        second_id,
        ImageMeta(
            "wf",
            "Cube",
            2,
            "",
            "E:/two.png",
            source_key="wf:node",
        ),
    )

    service.output_canvas_state_service.set_active_output_uuid(workflow, str(second_id))

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid == second_id
    assert workflow.active_output_set_index == 2
    assert workflow.active_output_source_key == "wf:node"
    assert workflow.active_output_scene_key is None
    assert workflow.active_output_scene_overview is False


def test_set_active_output_uuid_records_manual_scene_and_scene_local_set() -> None:
    """Concrete scene output selection should store scene-local source/set intent."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    scene1_first = uuid.uuid4()
    scene1_second = uuid.uuid4()
    scene2_first = uuid.uuid4()
    workflow.output_image_uuids = [scene1_first, scene1_second, scene2_first]
    for image_id, image_number, scene_key in (
        (scene1_first, 1, "scene1"),
        (scene1_second, 2, "scene1"),
        (scene2_first, 1, "scene2"),
    ):
        _store_image_record(
            service,
            image_id,
            ImageMeta(
                "wf",
                "Cube",
                image_number,
                "",
                f"E:/{scene_key}_{image_number}.png",
                source_key="wf:node",
                scene_key=scene_key,
            ),
        )

    service.output_canvas_state_service.set_active_output_uuid(
        workflow, str(scene2_first)
    )

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid == scene2_first
    assert workflow.active_output_set_index == 1
    assert workflow.active_output_source_key == "wf:node"
    assert workflow.active_output_scene_key == "scene2"
    assert workflow.active_output_scene_overview is False


def test_set_active_output_grid_records_manual_grid_intent() -> None:
    """Grid selection should store manual set-zero focus intent."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    workflow.active_output_uuid = uuid.uuid4()

    service.output_canvas_state_service.set_active_output_grid(workflow, "wf:node")

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid is None
    assert workflow.active_output_set_index == 0
    assert workflow.active_output_source_key == "wf:node"
    assert workflow.active_output_scene_key is None
    assert workflow.active_output_scene_overview is False


def test_set_active_output_scene_records_manual_scene_intent() -> None:
    """Scene selection should store manual scene focus separately from source focus."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    workflow.active_output_uuid = uuid.uuid4()
    workflow.active_output_source_key = "wf:node"
    workflow.active_output_set_index = 0

    service.output_canvas_state_service.set_active_output_scene(
        workflow,
        OutputSceneNavigationSelection(
            scene_key="scene2",
            overview=False,
            source_key="wf:node",
            set_index=0,
            image_id=None,
        ),
    )

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_scene_key == "scene2"
    assert workflow.active_output_scene_overview is False
    assert workflow.active_output_source_key == "wf:node"
    assert workflow.active_output_set_index == 0
    assert workflow.active_output_uuid is None


def test_set_active_output_scene_overview_records_manual_all_intent() -> None:
    """All scene selection should clear source focus and store overview intent."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    workflow.active_output_uuid = uuid.uuid4()
    workflow.active_output_source_key = "wf:node"
    workflow.active_output_set_index = 0

    service.output_canvas_state_service.set_active_output_scene(
        workflow,
        OutputSceneNavigationSelection(
            scene_key=None,
            overview=True,
            source_key=None,
            set_index=1,
            image_id=None,
        ),
    )

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid is None
    assert workflow.active_output_source_key is None
    assert workflow.active_output_set_index == 1
    assert workflow.active_output_scene_key is None
    assert workflow.active_output_scene_overview is True


def test_set_output_compare_state_persists_workflow_compare_state() -> None:
    """Canvas state service should store workflow-owned compare state."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection("scene-b", 2, "source-b"),
    )

    service.output_canvas_state_service.set_output_compare_state(workflow, state)

    assert workflow.output_compare_state == state


def test_project_workflow_restores_scene_focus_per_workflow() -> None:
    """Projecting workflows should not leak scene/source focus between them."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    workflow_a = WorkflowState()
    workflow_b = WorkflowState()
    a_scene1 = uuid.uuid4()
    a_scene2 = uuid.uuid4()
    b_scene1_first = uuid.uuid4()
    b_scene2_first = uuid.uuid4()
    b_scene2_second = uuid.uuid4()
    workflow_a.output_image_uuids = [a_scene1, a_scene2]
    workflow_a.output_focus_mode = OutputFocusMode.MANUAL
    workflow_a.active_output_scene_overview = True
    workflow_b.output_image_uuids = [b_scene1_first, b_scene2_first, b_scene2_second]
    workflow_b.output_focus_mode = OutputFocusMode.MANUAL
    workflow_b.active_output_scene_key = "scene2"
    workflow_b.active_output_scene_overview = False
    workflow_b.active_output_source_key = "wf-b:text"
    workflow_b.active_output_set_index = 0
    scene_records = {
        a_scene1: ImageMeta(
            "wf-a",
            "Text",
            1,
            "",
            "E:/a1.png",
            source_key="wf-a:text",
            scene_key="scene1",
            scene_title="A One",
            scene_order=0,
            scene_count=2,
        ),
        a_scene2: ImageMeta(
            "wf-a",
            "Text",
            1,
            "",
            "E:/a2.png",
            source_key="wf-a:text",
            scene_key="scene2",
            scene_title="A Two",
            scene_order=1,
            scene_count=2,
        ),
        b_scene1_first: ImageMeta(
            "wf-b",
            "Text",
            1,
            "",
            "E:/b1.png",
            source_key="wf-b:text",
            scene_key="scene1",
            scene_title="B One",
            scene_order=0,
            scene_count=2,
        ),
        b_scene2_first: ImageMeta(
            "wf-b",
            "Text",
            1,
            "",
            "E:/b2a.png",
            source_key="wf-b:text",
            scene_key="scene2",
            scene_title="B Two",
            scene_order=1,
            scene_count=2,
        ),
        b_scene2_second: ImageMeta(
            "wf-b",
            "Text",
            2,
            "",
            "E:/b2b.png",
            source_key="wf-b:text",
            scene_key="scene2",
            scene_title="B Two",
            scene_order=1,
            scene_count=2,
        ),
    }
    for image_id, image_meta in scene_records.items():
        _store_image_record(service, image_id, image_meta)
    workflows = {"A": workflow_a, "B": workflow_b}

    service.project_workflow(workflows, "A")
    projection_a_first = output_canvas.sync_calls[-1]
    service.project_workflow(workflows, "B")
    projection_b = output_canvas.sync_calls[-1]
    service.project_workflow(workflows, "A")
    projection_a_second = output_canvas.sync_calls[-1]

    assert projection_a_first.active_scene_overview is True
    assert projection_a_first.active_source_key is None
    assert projection_b.active_scene_overview is False
    assert projection_b.active_scene_key == "scene2"
    assert projection_b.active_source_key == "wf-b:text"
    assert projection_b.active_set_index == 0
    assert projection_a_second.active_scene_overview is True
    assert projection_a_second.active_source_key is None
    assert workflow_a.active_output_source_key is None
    assert workflow_b.active_output_source_key == "wf-b:text"


def test_inactive_scene_output_updates_origin_without_projecting_active_canvas() -> (
    None
):
    """Inactive workflow scene outputs should not overwrite active canvas projection."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    active_workflow = WorkflowState()
    inactive_workflow = WorkflowState()
    workflows = {"active": active_workflow, "inactive": inactive_workflow}

    _add_output_image(
        service,
        workflows,
        origin_workflow_id="inactive",
        active_workflow_id="active",
        image=object(),
        image_meta=ImageMeta(
            "inactive",
            "Text",
            1,
            "",
            "E:/inactive.png",
            source_key="inactive:text",
            source_label="Inactive Text",
            scene_run_id="run-inactive",
            scene_key="scene2",
            scene_title="Inactive Two",
            scene_order=1,
            scene_count=2,
        ),
    )

    assert output_canvas.sync_calls == []
    assert inactive_workflow.output_image_uuids
    assert inactive_workflow.active_output_source_key is None
    assert inactive_workflow.active_output_scene_key is None
    assert inactive_workflow.active_output_scene_overview is True
    assert active_workflow.active_output_source_key is None
    assert active_workflow.active_output_scene_key is None


def test_create_mask_for_image_tracks_explicit_image_association() -> None:
    """Blank mask creation should associate the created mask with the explicit image."""
    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    association_key = ("AliasB", "MaskNode")
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    input_pane.next_blank_mask_id = mask_id
    workflow.canvas.input_key_map["AliasB:ImageNode"] = image_id
    workflow.canvas.input_image_uuid = image_id

    created = input_service.create_mask_for_image(
        "wf",
        workflow,
        association_key,
        image_id,
        "size-token",
    )

    assert created == mask_id
    assert input_pane.current_id == image_id
    assert workflow.canvas.mask_associations[association_key] == mask_id
    assert workflow.canvas.mask_to_image_map[mask_id] == image_id


def test_drop_input_surface_prunes_owned_image_and_mask_state() -> None:
    """Synthetic invalidation should remove its image, masks, and active route state."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    input_key = "Regional:@synthetic/obsolete"
    association_key = ("Regional", "mask")
    workflow.canvas.input_key_map[input_key] = image_id
    workflow.canvas.input_image_uuid = image_id
    workflow.canvas.active_input_mask_uuid = mask_id
    workflow.canvas.mask_associations[association_key] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = image_id
    input_pane.images[image_id] = (object(), Path("synthetic.png"))

    dropped = input_service.drop_input_surface(
        {"wf": workflow},
        "wf",
        input_key,
    )

    assert dropped is True
    assert workflow.canvas.input_key_map == {}
    assert workflow.canvas.input_image_uuid is None
    assert workflow.canvas.active_input_mask_uuid is None
    assert workflow.canvas.mask_associations == {}
    assert workflow.canvas.mask_to_image_map == {}
    assert input_pane.removed_masks == [(image_id, mask_id)]
    assert image_id not in input_pane.images


def test_prune_closed_workflow_input_images_cleans_input_catalog_and_metadata() -> None:
    """Closed-workflow Input pruning should remove unreferenced Input payloads."""

    service, input_service, input_pane, output_pane, output_canvas = _build_services()
    orphan = uuid.uuid4()
    input_pane.images[orphan] = ("in", None)
    output_pane.images[orphan] = ("out", None)
    closed_workflow = WorkflowState()
    closed_workflow.canvas.input_key_map["Cube:Image"] = orphan
    _store_image_record(service, orphan, ImageMeta("wf", "cube", 7, "", ""))

    input_service.prune_closed_workflow_images(closed_workflow, {"wf": WorkflowState()})

    assert orphan not in input_pane.images
    assert orphan in output_pane.images
    assert service.image_registry.metadata_for(orphan) is None
    assert output_canvas.sync_calls == []
