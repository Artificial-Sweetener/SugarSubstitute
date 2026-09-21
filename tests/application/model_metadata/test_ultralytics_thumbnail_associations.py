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

"""Test authoritative Ultralytics thumbnail preference behavior."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from substitute.application.model_metadata.ultralytics_thumbnail_associations import (
    UltralyticsThumbnailAssociationService,
)
from substitute.application.model_metadata.ultralytics_visual_catalog import (
    ultralytics_visual_resolution,
)


class _MemoryRepository:
    """Persist associations in memory for application-service tests."""

    def __init__(self, values: Mapping[str, str] | None = None) -> None:
        """Initialize the fake with optional persisted values."""

        self.values = dict(values or {})

    def load(self) -> Mapping[str, str]:
        """Return the current persisted mapping."""

        return dict(self.values)

    def save(self, associations: Mapping[str, str]) -> None:
        """Replace the current persisted mapping."""

        self.values = dict(associations)


def test_explicit_association_overrides_default_visual_without_changing_value() -> None:
    """A library choice should affect presentation only, not backend identity."""

    repository = _MemoryRepository()
    service = UltralyticsThumbnailAssociationService(repository)
    backend_value = "bbox/face.pt"

    service.assign(backend_value, "hand-segmentation")
    resolution = ultralytics_visual_resolution(
        (backend_value,),
        thumbnail_associations=service.associations(),
    )

    assert repository.values == {backend_value: "hand-segmentation"}
    assert resolution.items[0].value == backend_value
    assert (
        resolution.items[0].thumbnail_variants[0].storage_key
        == "bundled:ultralytics:hand-segmentation"
    )


def test_invalid_asset_is_rejected_without_mutating_preferences() -> None:
    """Only packaged library assets should be eligible for association."""

    repository = _MemoryRepository()
    service = UltralyticsThumbnailAssociationService(repository)

    with pytest.raises(ValueError, match="Unknown bundled"):
        service.assign("bbox/face.pt", "not-packaged")

    assert repository.values == {}


def test_invalid_persisted_entries_are_ignored() -> None:
    """Malformed stale preferences should not suppress default enrichment."""

    service = UltralyticsThumbnailAssociationService(
        _MemoryRepository(
            {
                "bbox/face.pt": "missing",
                "segm/person.pt": "person-segmentation",
                "": "face-detection",
            }
        )
    )

    assert service.associations() == {
        "segm/person.pt": "person-segmentation",
    }
