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

"""Verify user-preset service prompt strings behavior."""

from __future__ import annotations

from .support import (
    GLOBAL_PRESET_ASSOCIATION,
    PromptStringPresetPayload,
    UserPresetKind,
    UserPresetService,
    _MemoryRepository,
    _checkpoint,
    _family,
    _prompt_preset,
    _service,
)


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
