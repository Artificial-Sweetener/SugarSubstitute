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

"""Characterize canvas projection closed workflow cleanup contracts."""

from __future__ import annotations

import uuid


from substitute.domain.workflow import (
    ImageMeta,
    OutputFocusMode,
    WorkflowState,
)


from ..support.harness import (
    _build_service,
    _build_services,
    _store_image_record,
)


def test_clear_images_for_closed_workflow_keeps_shared_references() -> None:
    """Closing a workflow removes only UUIDs no longer referenced by others."""
    service, input_service, input_pane, output_pane, _output_canvas = _build_services()
    wf_closed = WorkflowState()
    wf_remaining = WorkflowState()

    shared_id = uuid.uuid4()
    closed_only_id = uuid.uuid4()

    wf_closed.canvas.bind_image("A:img", closed_only_id)
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


def test_prune_closed_workflow_input_images_cleans_input_catalog_and_metadata() -> None:
    """Closed-workflow Input pruning should remove unreferenced Input payloads."""

    service, input_service, input_pane, output_pane, output_canvas = _build_services()
    orphan = uuid.uuid4()
    input_pane.images[orphan] = ("in", None)
    output_pane.images[orphan] = ("out", None)
    closed_workflow = WorkflowState()
    closed_workflow.canvas.bind_image("Cube:Image", orphan)
    _store_image_record(service, orphan, ImageMeta("wf", "cube", 7, "", ""))

    input_service.prune_closed_workflow_images(closed_workflow, {"wf": WorkflowState()})

    assert orphan not in input_pane.images
    assert orphan in output_pane.images
    assert service.image_registry.metadata_for(orphan) is None
    assert output_canvas.sync_calls == []
