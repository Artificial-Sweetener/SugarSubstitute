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

"""Characterize canvas projection registry identity contracts."""

from __future__ import annotations

import uuid
from pathlib import Path


from substitute.domain.workflow import (
    ImageMeta,
    WorkflowState,
)


from ..support.harness import (
    _build_service,
    _build_services,
    _store_image_record,
)


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

    changed = service.output_canvas_timing_service.apply_output_source_timing(
        workflows,
        workflow_id="wf",
        active_workflow_id="wf",
        source_durations_ms={"wf:save": 3080.0},
        cube_durations_ms={},
    )

    assert changed.changed is True
    assert changed.projection_intent.should_schedule is True
    assert workflow.output_image_uuids == [result.image_id]
    assert result.image_id is not None
    stored_meta = service.image_registry.metadata_for(result.image_id)
    assert stored_meta is not None
    assert stored_meta.cube_execution_duration_ms == 3080.0
    assert output_canvas.sync_calls == []


def test_load_input_image_replaces_pixels_without_replacing_entry_identity() -> None:
    """Replacing an input file preserves its document-owned image identity."""
    service, input_service, input_pane, _output_pane, _output_canvas = _build_services()
    workflow = WorkflowState()
    old_id = uuid.uuid4()
    workflow.canvas.bind_image("A:node", old_id)
    workflow.canvas.input_image_uuid = old_id
    input_pane.images[old_id] = ("old", Path("old.png"))
    _store_image_record(service, old_id, ImageMeta("wf", "Cube", 1, "", ""))

    new_image = object()
    image_id = input_service.load_input_image(
        {"wf": workflow},
        "wf",
        "A:node",
        image=new_image,
        path=Path("new.png"),
    )

    assert image_id == old_id
    assert input_pane.images[old_id] == (new_image, Path("new.png"))
    assert service.image_registry.metadata_for(old_id) is not None
    image_entry = workflow.canvas.image_entry("A:node")
    assert image_entry is not None
    assert image_entry.image_id == old_id
    assert workflow.canvas.input_image_uuid == old_id
    assert input_pane.current_id == old_id


def test_load_input_image_keeps_entry_identity_when_also_referenced_as_output() -> None:
    """Pixel replacement preserves identity regardless of other registry references."""
    service, input_service, input_pane, _output_pane, _output_canvas = _build_services()
    workflow_a = WorkflowState()
    workflow_b = WorkflowState()
    old_id = uuid.uuid4()
    workflow_a.canvas.bind_image("A:node", old_id)
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
