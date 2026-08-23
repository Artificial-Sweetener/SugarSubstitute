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

"""Verify user-preset service dimension behavior."""

from __future__ import annotations

from .support import (
    DimensionPresetPayload,
    GLOBAL_PRESET_ASSOCIATION,
    _MemoryRepository,
    _family,
    _preset,
    _service,
)


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
