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

"""Test file-backed Ultralytics thumbnail preference persistence."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.persistence.file_ultralytics_thumbnail_association_repository import (
    FileUltralyticsThumbnailAssociationRepository,
)


def test_repository_round_trips_unicode_backend_values(tmp_path: Path) -> None:
    """Exact model identities should survive atomic JSON persistence."""

    repository = FileUltralyticsThumbnailAssociationRepository(tmp_path)
    associations = {
        "bbox/人物 face.pt": "face-detection",
        "segm/person.pt": "person-segmentation",
    }

    repository.save(associations)

    assert repository.load() == associations
    assert not tuple(tmp_path.glob("*.tmp"))


def test_repository_treats_corrupt_json_as_empty(tmp_path: Path) -> None:
    """Corrupt preferences should remain a recoverable empty state."""

    path = tmp_path / "ultralytics-thumbnail-associations.json"
    path.write_text("{not-json", encoding="utf-8")

    assert FileUltralyticsThumbnailAssociationRepository(tmp_path).load() == {}
