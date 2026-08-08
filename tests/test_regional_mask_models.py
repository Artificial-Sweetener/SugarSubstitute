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

"""Verify durable ordered regional-mask identity and selection behavior."""

from __future__ import annotations

from uuid import uuid4

import pytest

from substitute.domain.workflow import RegionalMaskCollection, WorkflowCanvasState


def test_collection_add_select_reorder_and_remove_preserve_region_identity() -> None:
    """Ordered operations should never replace stable region identities."""

    image_id = uuid4()
    collection = RegionalMaskCollection(("Prompt by Region", "load_mask_batch"))
    first = collection.add_region(image_id, mask_id=uuid4())
    second = collection.add_region(image_id, mask_id=uuid4())
    third = collection.add_region(image_id, mask_id=uuid4())

    collection.reorder(third.region_id, 0)
    collection.select(first.region_id)
    removed = collection.remove(first.region_id)

    assert removed == first
    assert [entry.region_id for entry in collection.entries] == [
        third.region_id,
        second.region_id,
    ]
    assert collection.selected_region_id == second.region_id


def test_collection_supports_region_identity_before_canvas_materialization() -> None:
    """A region should exist before its blank CuteCanvas layer is available."""

    collection = RegionalMaskCollection(("cube", "masks"))
    region = collection.add_region(uuid4())
    mask_id = uuid4()

    bound = collection.bind_mask_layer(region.region_id, mask_id)

    assert bound.mask_id == mask_id
    assert collection.entry_for_mask(mask_id) == bound


def test_workflow_canvas_owns_scalar_and_ordered_mask_layers() -> None:
    """Canvas ownership should include both legacy scalar and regional layers."""

    canvas = WorkflowCanvasState()
    image_id = uuid4()
    scalar_mask_id = uuid4()
    regional_mask_id = uuid4()
    canvas.bind_mask(("cube", "scalar"), scalar_mask_id, image_id)
    collection = canvas.ensure_regional_mask_collection(("cube", "batch"))
    collection.add_region(image_id, mask_id=regional_mask_id)

    assert canvas.owns_mask(scalar_mask_id, image_id)
    assert canvas.owns_mask(regional_mask_id, image_id)
    assert set(canvas.mask_ids()) == {scalar_mask_id, regional_mask_id}
    assert canvas.mask_image_owners() == {
        scalar_mask_id: image_id,
        regional_mask_id: image_id,
    }


def test_canvas_resampling_remaps_mask_resources_without_reordering_regions() -> None:
    """Resource replacement should preserve scalar, region, and active identity."""

    canvas = WorkflowCanvasState()
    image_id = uuid4()
    old_scalar_id, old_first_id, old_second_id = uuid4(), uuid4(), uuid4()
    new_scalar_id, new_first_id, new_second_id = uuid4(), uuid4(), uuid4()
    canvas.bind_mask(("cube", "scalar"), old_scalar_id, image_id)
    collection = canvas.ensure_regional_mask_collection(("cube", "batch"))
    first = collection.add_region(image_id, mask_id=old_first_id)
    second = collection.add_region(image_id, mask_id=old_second_id)
    canvas.active_input_mask_uuid = old_second_id

    assert canvas.remap_mask_ids(
        image_id,
        (
            (old_scalar_id, new_scalar_id),
            (old_first_id, new_first_id),
            (old_second_id, new_second_id),
        ),
    )

    scalar_entry = canvas.mask_entry(("cube", "scalar"))
    assert scalar_entry is not None and scalar_entry.mask_id == new_scalar_id
    assert [entry.region_id for entry in collection.entries] == [
        first.region_id,
        second.region_id,
    ]
    assert [entry.mask_id for entry in collection.entries] == [
        new_first_id,
        new_second_id,
    ]
    assert canvas.active_input_mask_uuid == new_second_id


def test_canvas_mask_remap_rejects_foreign_or_colliding_resources_atomically() -> None:
    """Invalid replacement sets should leave every workflow identity untouched."""

    canvas = WorkflowCanvasState()
    image_id = uuid4()
    first_id, second_id = uuid4(), uuid4()
    canvas.bind_mask(("cube", "first"), first_id, image_id)
    canvas.bind_mask(("cube", "second"), second_id, image_id)

    with pytest.raises(ValueError, match="target already belongs"):
        canvas.remap_mask_ids(image_id, ((first_id, second_id),))

    assert canvas.mask_ids() == (first_id, second_id)


def test_collection_rejects_duplicate_mask_layer_identity() -> None:
    """One CuteCanvas layer cannot represent two authored regions."""

    collection = RegionalMaskCollection(("cube", "batch"))
    image_id = uuid4()
    mask_id = uuid4()
    collection.add_region(image_id, mask_id=mask_id)

    with pytest.raises(ValueError, match="Mask layer"):
        collection.add_region(image_id, mask_id=mask_id)
