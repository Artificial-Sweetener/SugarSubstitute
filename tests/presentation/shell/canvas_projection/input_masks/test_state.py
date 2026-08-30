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

"""Characterize canvas projection input mask contracts."""

from __future__ import annotations

import uuid
from pathlib import Path


from substitute.domain.workflow import (
    WorkflowState,
)


from ..support.harness import (
    _build_service,
    _build_services,
)


def test_set_active_input_image_rejects_uuid_not_owned_by_active_workflow() -> None:
    """Input route activation rejects non-owned image UUIDs."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    owned_image = uuid.uuid4()
    foreign_image = uuid.uuid4()
    input_pane.current_id = owned_image

    workflow = WorkflowState()
    workflow.canvas.bind_image("Cube:Image", owned_image)
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
    workflow.canvas.bind_mask(("Cube", "Mask"), stale_mask, stale_image)

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
    workflow.canvas.bind_mask(("Cube", "Mask"), foreign_mask, foreign_image)

    input_service.set_active_workflow_mask("wf", workflow, foreign_mask)

    assert workflow.canvas.active_input_mask_uuid is None
    assert input_pane.active_mask is None


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
    workflow.canvas.bind_image("AliasA:ImageNode", image_id)
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
    mask_entry = workflow.canvas.mask_entry(association_key)
    assert mask_entry is not None
    assert mask_entry.mask_id == mask_id
    assert mask_entry.image_id == image_id


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
    workflow.canvas.bind_image("AliasA:ImageNode", image_id)
    workflow.canvas.input_image_uuid = image_id
    workflow.canvas.bind_mask(association_key, snapshot_mask_id, image_id)
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
    mask_entry = workflow.canvas.mask_entry(association_key)
    assert mask_entry is not None
    assert mask_entry.mask_id == live_mask_id
    assert mask_entry.image_id == image_id
    assert workflow.canvas.mask_entry_for_id(snapshot_mask_id) is None
    assert workflow.canvas.active_input_mask_uuid == live_mask_id


def test_restore_input_mask_adopts_exact_editable_archive_identity() -> None:
    """Complete document restore should bypass flattened mask-file import."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    association_key = ("AliasA", "MaskNode")
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    input_pane.archived_masks.add((image_id, mask_id))
    workflow.canvas.bind_image("AliasA:ImageNode", image_id)
    workflow.canvas.input_image_uuid = image_id
    workflow.canvas.bind_mask(association_key, mask_id, image_id)
    workflow.canvas.active_input_mask_uuid = mask_id

    restored = input_service.restore_input_mask(
        "wf",
        workflow,
        snapshot_mask_id=mask_id,
        image_id=image_id,
        path=Path("missing-flat-mask.png"),
        association_key=association_key,
    )

    assert restored == mask_id
    assert input_pane.next_loaded_mask_id is None
    mask_entry = workflow.canvas.mask_entry(association_key)
    assert mask_entry is not None
    assert mask_entry.mask_id == mask_id
    assert workflow.canvas.active_input_mask_uuid == mask_id


def test_restore_archived_mask_routes_its_composition_before_applying_opacity() -> None:
    """Inactive restored masks should receive presentation in their own document."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    association_key = ("AliasA", "MaskNode")
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    input_pane.archived_masks.add((image_id, mask_id))
    input_pane.current_id = uuid.uuid4()
    workflow.canvas.bind_image("AliasA:ImageNode", image_id)
    workflow.canvas.input_image_uuid = image_id
    workflow.canvas.bind_mask(association_key, mask_id, image_id)
    workflow.canvas.mask_visual_opacities[association_key] = 0.8

    restored = input_service.restore_input_mask(
        "wf",
        workflow,
        snapshot_mask_id=mask_id,
        image_id=image_id,
        path=Path("missing-flat-mask.png"),
        association_key=association_key,
    )

    assert restored == mask_id
    assert input_pane.mask_opacity_calls == [(image_id, mask_id, 0.8)]


def test_restore_input_mask_remaps_ordered_region_without_creating_scalar_entry() -> (
    None
):
    """Ordered mask restore should preserve region identity and collection order."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    association_key = ("AliasA", "MaskBatch")
    image_id = uuid.uuid4()
    snapshot_mask_ids = (uuid.uuid4(), uuid.uuid4())
    live_mask_id = uuid.uuid4()
    input_pane.next_loaded_mask_id = live_mask_id
    workflow.canvas.bind_image("AliasA:@synthetic", image_id)
    workflow.canvas.input_image_uuid = image_id
    collection = workflow.canvas.ensure_regional_mask_collection(association_key)
    first = collection.add_region(image_id, mask_id=snapshot_mask_ids[0])
    second = collection.add_region(image_id, mask_id=snapshot_mask_ids[1])
    workflow.canvas.active_input_mask_uuid = snapshot_mask_ids[0]

    restored = input_service.restore_input_mask(
        "wf",
        workflow,
        snapshot_mask_id=snapshot_mask_ids[0],
        image_id=image_id,
        path=Path("region-1.png"),
        association_key=association_key,
    )

    assert restored == live_mask_id
    assert tuple(entry.region_id for entry in collection.entries) == (
        first.region_id,
        second.region_id,
    )
    assert tuple(entry.mask_id for entry in collection.entries) == (
        live_mask_id,
        snapshot_mask_ids[1],
    )
    assert workflow.canvas.mask_entry(association_key) is None
    assert workflow.canvas.active_input_mask_uuid == live_mask_id


def test_project_workflow_restores_active_input_mask() -> None:
    """Workflow projection should restore the selected input mask for its image."""
    service, input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    workflow.canvas.input_image_uuid = image_id
    workflow.canvas.bind_image("AliasA:ImageNode", image_id)
    workflow.canvas.bind_mask(("AliasA", "MaskNode"), mask_id, image_id)
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
    workflow.canvas.bind_mask(association_key, mask_id, image_id)

    input_service.drop_mask_association(workflow, association_key)

    assert workflow.canvas.mask_entry(association_key) is None
    assert workflow.canvas.mask_entry_for_id(mask_id) is None
    assert input_pane.removed_masks == [(image_id, mask_id)]


def test_drop_mask_association_preserves_shared_pane_layer() -> None:
    """A still-referenced mask layer should stay attached to the pane."""
    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    workflow.canvas.bind_mask(("AliasA", "MaskNodeA"), mask_id, image_id)
    workflow.canvas.bind_mask(("AliasA", "MaskNodeB"), mask_id, image_id)

    input_service.drop_mask_association(workflow, ("AliasA", "MaskNodeA"))

    assert workflow.canvas.mask_entry(("AliasA", "MaskNodeA")) is None
    remaining_entry = workflow.canvas.mask_entry(("AliasA", "MaskNodeB"))
    assert remaining_entry is not None
    assert remaining_entry.mask_id == mask_id
    assert remaining_entry.image_id == image_id
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
    workflow.canvas.bind_image("Cube:Image", image_id)
    workflow.canvas.bind_mask(("Cube", "Mask"), mask_id, foreign_image)

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
    workflow.canvas.bind_image("Cube:Image", image_id)
    workflow.canvas.bind_mask(("Cube", "Mask"), mask_id, image_id)

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
    assert input_pane.updated_masks == [(mask_id, Path("mask.png"))]


def test_update_mask_from_file_rejects_unverified_dimensions() -> None:
    """Mask pixel updates should fail closed when dimensions are unavailable."""

    _service, input_service, input_pane, _output_pane, _output_canvas = (
        _build_services()
    )
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    mask_id = uuid.uuid4()
    workflow.canvas.bind_image("Cube:Image", image_id)
    workflow.canvas.bind_mask(("Cube", "Mask"), mask_id, image_id)

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
    workflow.canvas.bind_image("Cube:Image", image_id)
    workflow.canvas.bind_mask(("Cube", "Mask"), mask_id, image_id)

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
    workflow.canvas.bind_image("AliasB:ImageNode", image_id)
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
    mask_entry = workflow.canvas.mask_entry(association_key)
    assert mask_entry is not None
    assert mask_entry.mask_id == mask_id
    assert mask_entry.image_id == image_id


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
    workflow.canvas.bind_image(input_key, image_id)
    workflow.canvas.input_image_uuid = image_id
    workflow.canvas.active_input_mask_uuid = mask_id
    workflow.canvas.bind_mask(association_key, mask_id, image_id)
    input_pane.images[image_id] = (object(), Path("synthetic.png"))

    dropped = input_service.drop_input_surface(
        {"wf": workflow},
        "wf",
        input_key,
    )

    assert dropped is True
    assert workflow.canvas.image_entries == {}
    assert workflow.canvas.input_image_uuid is None
    assert workflow.canvas.active_input_mask_uuid is None
    assert workflow.canvas.mask_entries == {}
    assert input_pane.removed_masks == [(image_id, mask_id)]
    assert image_id not in input_pane.images
