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

"""Contract tests for user preset application service behavior."""

from __future__ import annotations

from substitute.application.user_presets import UserPresetService
from substitute.domain.user_presets import (
    DimensionPresetPayload,
    GLOBAL_PRESET_ASSOCIATION,
    NodeInputPresetPayload,
    PromptStringPresetPayload,
    UserPreset,
    UserPresetAssociation,
    UserPresetAssociationScope,
    UserPresetKind,
)


class _MemoryRepository:
    """Store user presets in memory for service tests."""

    def __init__(self, presets: tuple[UserPreset, ...] = ()) -> None:
        """Initialize stored presets."""

        self.presets = presets
        self.save_calls: list[tuple[UserPreset, ...]] = []

    def load_presets(self) -> tuple[UserPreset, ...]:
        """Return stored presets."""

        return self.presets

    def save_presets(self, presets: tuple[UserPreset, ...]) -> None:
        """Persist presets in memory and record the call."""

        self.presets = presets
        self.save_calls.append(presets)


def test_save_dimension_preset_creates_canonical_shape() -> None:
    """Saving dimensions should create a canonical shape preset."""

    repository = _MemoryRepository()
    service = _service(repository)

    preset = service.save_dimension_preset(
        width=1024,
        height=1536,
        association=GLOBAL_PRESET_ASSOCIATION,
    )

    assert preset.payload == DimensionPresetPayload(short_edge=1024, long_edge=1536)
    assert preset.label == "1024 x 1536"
    assert repository.presets == (preset,)


def test_save_dimension_preset_merges_orientation_duplicates() -> None:
    """Saving the same shape in another orientation should merge associations."""

    repository = _MemoryRepository()
    service = _service(repository)

    first = service.save_dimension_preset(
        width=1024,
        height=1536,
        association=GLOBAL_PRESET_ASSOCIATION,
    )
    second = service.save_dimension_preset(
        width=1536,
        height=1024,
        association=_family("illustrious", "Illustrious"),
    )

    assert len(repository.presets) == 1
    assert second.id == first.id
    assert second.associations == (
        GLOBAL_PRESET_ASSOCIATION,
        _family("illustrious", "Illustrious"),
    )


def test_save_dimension_preset_does_not_duplicate_existing_association() -> None:
    """Saving the same association twice should not rewrite duplicate entries."""

    repository = _MemoryRepository()
    service = _service(repository)
    association = _family("illustrious", "Illustrious")

    first = service.save_dimension_preset(
        width=1024,
        height=1536,
        association=association,
    )
    second = service.save_dimension_preset(
        width=1536,
        height=1024,
        association=association,
    )

    assert second == first
    assert second.associations == (association,)
    assert len(repository.save_calls) == 1


def test_save_dimension_preset_matches_association_by_target_not_label() -> None:
    """Saving the same family target with a new label should not duplicate it."""

    repository = _MemoryRepository()
    service = _service(repository)

    first = service.save_dimension_preset(
        width=1024,
        height=1536,
        association=_family("illustrious", "Illustrious"),
    )
    second = service.save_dimension_preset(
        width=1536,
        height=1024,
        association=_family("illustrious", "Illustrious XL"),
    )

    assert second == first
    assert second.associations == (_family("illustrious", "Illustrious"),)
    assert len(repository.save_calls) == 1


def test_list_dimension_presets_splits_global_and_matching_family() -> None:
    """Listing should return global presets and matching family sections."""

    global_preset = _preset(
        "dimension:global",
        short_edge=832,
        long_edge=1216,
        associations=(GLOBAL_PRESET_ASSOCIATION,),
    )
    illustrious = _family("illustrious", "Illustrious")
    family_preset = _preset(
        "dimension:family",
        short_edge=1024,
        long_edge=1536,
        associations=(illustrious,),
    )
    repository = _MemoryRepository((family_preset, global_preset))
    service = _service(repository)

    listing = service.list_dimension_presets((illustrious,))

    assert listing.global_presets == (global_preset,)
    assert len(listing.association_sections) == 1
    assert listing.association_sections[0].association == illustrious
    assert listing.association_sections[0].presets == (family_preset,)


def test_list_dimension_presets_matches_association_by_target_not_label() -> None:
    """Listing should use scope/provider/key rather than the stored display label."""

    repository = _MemoryRepository(
        (
            _preset(
                "dimension:family",
                short_edge=1024,
                long_edge=1536,
                associations=(_family("illustrious", "Illustrious"),),
            ),
        )
    )
    service = _service(repository)

    listing = service.list_dimension_presets(
        (_family("illustrious", "Illustrious XL"),)
    )

    assert len(listing.association_sections) == 1
    assert listing.association_sections[0].presets == repository.presets


def test_list_dimension_presets_omits_unmatched_family_presets() -> None:
    """Listing for one family should not include another family's presets."""

    noobai = _family("noobai", "NoobAI")
    repository = _MemoryRepository(
        (
            _preset(
                "dimension:family",
                short_edge=1024,
                long_edge=1536,
                associations=(_family("illustrious", "Illustrious"),),
            ),
        )
    )
    service = _service(repository)

    listing = service.list_dimension_presets((noobai,))

    assert listing.global_presets == ()
    assert listing.association_sections == ()


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


def test_save_prompt_string_preset_creates_global_preset() -> None:
    """Saving selected prompt text should create a named prompt string preset."""

    repository = _MemoryRepository()
    service = _service(repository)

    preset = service.save_prompt_string_preset(
        label="Blue eyes",
        text="blue eyes",
        association=GLOBAL_PRESET_ASSOCIATION,
    )

    assert preset.kind is UserPresetKind.PROMPT_STRING
    assert preset.label == "Blue eyes"
    assert preset.payload == PromptStringPresetPayload(text="blue eyes")
    assert preset.associations == (GLOBAL_PRESET_ASSOCIATION,)
    assert repository.presets == (preset,)


def test_save_prompt_string_preset_rejects_blank_label() -> None:
    """Prompt segment names should be meaningful."""

    repository = _MemoryRepository()
    service = _service(repository)

    try:
        service.save_prompt_string_preset(
            label=" ",
            text="blue eyes",
            association=GLOBAL_PRESET_ASSOCIATION,
        )
    except ValueError as error:
        assert "label" in str(error)
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("blank labels should fail")


def test_save_prompt_string_preset_rejects_blank_text() -> None:
    """Prompt segments should contain at least one non-whitespace character."""

    repository = _MemoryRepository()
    service = _service(repository)

    try:
        service.save_prompt_string_preset(
            label="Blank",
            text="   ",
            association=GLOBAL_PRESET_ASSOCIATION,
        )
    except ValueError as error:
        assert "text" in str(error)
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("blank text should fail")


def test_save_prompt_string_preset_merges_duplicate_text() -> None:
    """Saving the same selected text for another scope should merge associations."""

    repository = _MemoryRepository()
    service = _service(repository)

    first = service.save_prompt_string_preset(
        label="Blue eyes",
        text="blue eyes",
        association=GLOBAL_PRESET_ASSOCIATION,
    )
    second = service.save_prompt_string_preset(
        label="Blue eyes model",
        text="blue eyes",
        association=_family("illustrious", "Illustrious"),
    )

    assert len(repository.presets) == 1
    assert second.id == first.id
    assert second.label == "Blue eyes model"
    assert second.associations == (
        GLOBAL_PRESET_ASSOCIATION,
        _family("illustrious", "Illustrious"),
    )


def test_save_prompt_string_preset_updates_same_association() -> None:
    """Saving the same text and target should update label and timestamp."""

    repository = _MemoryRepository()
    clock_values = iter(
        (
            "2026-04-20T12:00:00Z",
            "2026-04-20T12:05:00Z",
        )
    )
    service = UserPresetService(
        repository,
        id_factory=lambda: "prompt:test-1",
        clock=lambda: next(clock_values),
    )

    service.save_prompt_string_preset(
        label="Old",
        text="blue eyes",
        association=GLOBAL_PRESET_ASSOCIATION,
    )
    updated = service.save_prompt_string_preset(
        label="New",
        text="blue eyes",
        association=GLOBAL_PRESET_ASSOCIATION,
    )

    assert updated.label == "New"
    assert updated.updated_at == "2026-04-20T12:05:00Z"
    assert updated.associations == (GLOBAL_PRESET_ASSOCIATION,)


def test_list_prompt_string_presets_uses_specificity_order_and_dedupes() -> None:
    """Prompt listing should show each preset in the most specific matching section."""

    checkpoint = _checkpoint("123", "Exact checkpoint")
    family = _family("illustrious", "Illustrious")
    exact_preset = _prompt_preset(
        "prompt:exact",
        label="Exact",
        text="exact words",
        associations=(checkpoint,),
    )
    family_preset = _prompt_preset(
        "prompt:family",
        label="Family",
        text="family words",
        associations=(family, GLOBAL_PRESET_ASSOCIATION),
    )
    global_preset = _prompt_preset(
        "prompt:global",
        label="Global",
        text="global words",
        associations=(GLOBAL_PRESET_ASSOCIATION,),
    )
    repository = _MemoryRepository((global_preset, family_preset, exact_preset))
    service = _service(repository)

    listing = service.list_prompt_string_presets(
        (checkpoint, family, GLOBAL_PRESET_ASSOCIATION)
    )

    assert [section.title for section in listing.sections] == [
        "Exact checkpoint",
        "Illustrious",
        "Global",
    ]
    assert [section.presets for section in listing.sections] == [
        (exact_preset,),
        (family_preset,),
        (global_preset,),
    ]


def test_list_prompt_string_presets_sorts_actions_by_label() -> None:
    """Prompt presets inside one section should have deterministic label order."""

    repository = _MemoryRepository(
        (
            _prompt_preset(
                "prompt:b",
                label="Beta",
                text="beta",
                associations=(GLOBAL_PRESET_ASSOCIATION,),
            ),
            _prompt_preset(
                "prompt:a",
                label="Alpha",
                text="alpha",
                associations=(GLOBAL_PRESET_ASSOCIATION,),
            ),
        )
    )
    service = _service(repository)

    listing = service.list_prompt_string_presets((GLOBAL_PRESET_ASSOCIATION,))

    assert [preset.label for preset in listing.sections[0].presets] == [
        "Alpha",
        "Beta",
    ]


def _service(repository: _MemoryRepository) -> UserPresetService:
    """Return a deterministic user preset service."""

    ids = iter(
        (
            "preset:test-1",
            "preset:test-2",
            "preset:test-3",
            "preset:test-4",
        )
    )
    return UserPresetService(
        repository,
        id_factory=lambda: next(ids),
        clock=lambda: "2026-04-20T12:00:00Z",
    )


def _family(key: str, label: str) -> UserPresetAssociation:
    """Return one model-family association."""

    return UserPresetAssociation(
        scope=UserPresetAssociationScope.MODEL_FAMILY,
        provider="civitai",
        key=key,
        label=label,
    )


def _checkpoint(key: str, label: str) -> UserPresetAssociation:
    """Return one CivitAI model-version association."""

    return UserPresetAssociation(
        scope=UserPresetAssociationScope.PROVIDER_MODEL_VERSION,
        provider="civitai",
        key=key,
        label=label,
    )


def _preset(
    preset_id: str,
    *,
    short_edge: int,
    long_edge: int,
    associations: tuple[UserPresetAssociation, ...],
) -> UserPreset:
    """Return one deterministic dimension preset."""

    return UserPreset(
        id=preset_id,
        kind=UserPresetKind.DIMENSION,
        label=f"{short_edge} x {long_edge}",
        payload=DimensionPresetPayload(short_edge=short_edge, long_edge=long_edge),
        associations=associations,
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )


def _node_preset(
    preset_id: str,
    *,
    label: str,
    node_type: str,
    inputs: dict[str, object],
    associations: tuple[UserPresetAssociation, ...],
) -> UserPreset:
    """Return one deterministic node input preset."""

    return UserPreset(
        id=preset_id,
        kind=UserPresetKind.NODE_INPUTS,
        label=label,
        payload=NodeInputPresetPayload(node_type=node_type, inputs=inputs),
        associations=associations,
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )


def _prompt_preset(
    preset_id: str,
    *,
    label: str,
    text: str,
    associations: tuple[UserPresetAssociation, ...],
) -> UserPreset:
    """Return one deterministic prompt string preset."""

    return UserPreset(
        id=preset_id,
        kind=UserPresetKind.PROMPT_STRING,
        label=label,
        payload=PromptStringPresetPayload(text=text),
        associations=associations,
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )
