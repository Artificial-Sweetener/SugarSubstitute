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

"""Characterize canvas projection workflow route contracts."""

from __future__ import annotations

import uuid
from pathlib import Path


from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.domain.workflow import (
    CanvasKind,
    ImageMeta,
    WorkflowState,
)


from ..support.harness import (
    _add_output_image,
    _build_service,
    _store_image_record,
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
    workflow_a.canvas.bind_image("A:load", input_a)
    workflow_a.output_image_uuids = [output_a]
    workflow_a.active_output_uuid = output_a
    workflow_b.canvas.input_image_uuid = input_b
    workflow_b.canvas.bind_image("B:load", input_b)
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
    workflow_a.canvas.bind_image("A:load", input_a)
    workflow_a.output_image_uuids = [output_a]
    workflow_a.active_output_uuid = output_a
    workflow_b.canvas.input_image_uuid = input_b
    workflow_b.canvas.bind_image("B:load", input_b)
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
