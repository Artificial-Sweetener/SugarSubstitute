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

"""Verify user-preset service node inputs behavior."""

from __future__ import annotations

from .support import (
    GLOBAL_PRESET_ASSOCIATION,
    NodeInputPresetPayload,
    UserPresetKind,
    UserPresetService,
    _MemoryRepository,
    _family,
    _node_preset,
    _service,
)


def test_save_node_input_preset_creates_named_node_preset() -> None:
    """Saving node inputs should create a named node-type preset."""

    repository = _MemoryRepository()
    service = _service(repository)

    preset = service.save_node_input_preset(
        label="Fast Draft",
        node_type="KSampler",
        inputs={"steps": 20, "cfg": 7.0},
        association=GLOBAL_PRESET_ASSOCIATION,
    )

    assert preset.kind is UserPresetKind.NODE_INPUTS
    assert preset.label == "Fast Draft"
    assert preset.payload == NodeInputPresetPayload(
        node_type="KSampler",
        inputs={"steps": 20, "cfg": 7.0},
    )
    assert preset.associations == (GLOBAL_PRESET_ASSOCIATION,)
    assert repository.presets == (preset,)


def test_save_node_input_preset_updates_same_label_node_and_association() -> None:
    """Saving the same named node preset target should update stored inputs."""

    repository = _MemoryRepository()
    clock_values = iter(
        (
            "2026-04-20T12:00:00Z",
            "2026-04-20T12:05:00Z",
        )
    )
    service = UserPresetService(
        repository,
        id_factory=lambda: "node_inputs:test-1",
        clock=lambda: next(clock_values),
    )

    first = service.save_node_input_preset(
        label="Fast Draft",
        node_type="KSampler",
        inputs={"steps": 20},
        association=GLOBAL_PRESET_ASSOCIATION,
    )
    updated = service.save_node_input_preset(
        label=" fast draft ",
        node_type="KSampler",
        inputs={"steps": 12},
        association=GLOBAL_PRESET_ASSOCIATION,
    )

    assert len(repository.presets) == 1
    assert updated.id == first.id
    assert updated.created_at == "2026-04-20T12:00:00Z"
    assert updated.updated_at == "2026-04-20T12:05:00Z"
    assert updated.label == "fast draft"
    assert updated.payload == NodeInputPresetPayload(
        node_type="KSampler",
        inputs={"steps": 12},
    )


def test_save_node_input_preset_keeps_node_type_and_label_separate() -> None:
    """Node type and label are part of named node preset identity."""

    repository = _MemoryRepository()
    service = _service(repository)

    service.save_node_input_preset(
        label="Fast Draft",
        node_type="KSampler",
        inputs={"steps": 20},
        association=GLOBAL_PRESET_ASSOCIATION,
    )
    service.save_node_input_preset(
        label="Fast Draft",
        node_type="CheckpointLoaderSimple",
        inputs={"ckpt_name": "model.safetensors"},
        association=GLOBAL_PRESET_ASSOCIATION,
    )
    service.save_node_input_preset(
        label="Preview",
        node_type="KSampler",
        inputs={"steps": 20},
        association=GLOBAL_PRESET_ASSOCIATION,
    )

    assert len(repository.presets) == 3
    assert [preset.label for preset in repository.presets] == [
        "Fast Draft",
        "Fast Draft",
        "Preview",
    ]


def test_list_node_input_presets_filters_by_node_type_and_scope_order() -> None:
    """Listing should expose matching node presets by association order."""

    global_preset = _node_preset(
        "node_inputs:global",
        label="Balanced",
        node_type="KSampler",
        inputs={"steps": 20},
        associations=(GLOBAL_PRESET_ASSOCIATION,),
    )
    family = _family("illustrious", "Illustrious")
    family_preset = _node_preset(
        "node_inputs:family",
        label="Fast Draft",
        node_type="KSampler",
        inputs={"steps": 12},
        associations=(family, GLOBAL_PRESET_ASSOCIATION),
    )
    other_type_preset = _node_preset(
        "node_inputs:checkpoint",
        label="Checkpoint",
        node_type="CheckpointLoaderSimple",
        inputs={"ckpt_name": "model.safetensors"},
        associations=(GLOBAL_PRESET_ASSOCIATION,),
    )
    repository = _MemoryRepository((global_preset, family_preset, other_type_preset))
    service = _service(repository)

    listing = service.list_node_input_presets(
        node_type="KSampler",
        associations=(family, GLOBAL_PRESET_ASSOCIATION),
    )

    assert [section.association for section in listing.sections] == [
        family,
        GLOBAL_PRESET_ASSOCIATION,
    ]
    assert [section.presets for section in listing.sections] == [
        (family_preset,),
        (global_preset,),
    ]


def test_list_node_input_presets_matches_association_by_target_not_label() -> None:
    """Node preset listing should ignore stale association display labels."""

    repository = _MemoryRepository(
        (
            _node_preset(
                "node_inputs:family",
                label="Fast Draft",
                node_type="KSampler",
                inputs={"steps": 12},
                associations=(_family("illustrious", "Illustrious"),),
            ),
        )
    )
    service = _service(repository)

    listing = service.list_node_input_presets(
        node_type="KSampler",
        associations=(_family("illustrious", "Illustrious XL"),),
    )

    assert len(listing.sections) == 1
    assert listing.sections[0].presets == repository.presets
