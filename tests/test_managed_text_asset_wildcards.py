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

"""Tests for wildcard managed text asset adaptation."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.application.managed_text_assets import (
    CreateManagedTextAssetRequest,
    ManagedTextAssetKind,
    RenameManagedTextAssetRequest,
    WildcardManagedTextAssetService,
)
from substitute.application.prompt_wildcards import PromptWildcardFileManagementService
from substitute.infrastructure.persistence import FilePromptWildcardFileRepository


def test_wildcard_assets_map_txt_and_csv_metadata(tmp_path: Path) -> None:
    """Wildcard files should expose stable managed text asset metadata."""

    service = _service(tmp_path)
    service.create_asset(
        CreateManagedTextAssetRequest(
            label="characters/hair",
            kind=ManagedTextAssetKind.PROMPT_TEXT,
            content="blue\nred\n",
        )
    )
    service.create_asset(
        CreateManagedTextAssetRequest(label="poses", kind=ManagedTextAssetKind.CSV)
    )

    assets = service.list_assets()

    assert tuple(asset.id for asset in assets) == ("characters/hair.txt", "poses.csv")
    assert assets[0].label == "characters/hair"
    assert assets[0].group == "TXT Wildcards"
    assert assets[0].subtitle == "2 wildcards"
    assert "characters/hair.txt" not in assets[0].subtitle
    assert "enabled" not in assets[0].subtitle
    assert "disabled" not in assets[0].subtitle
    assert assets[0].kind is ManagedTextAssetKind.PROMPT_TEXT
    assert assets[1].group == "CSV Wildcards"
    assert assets[1].kind is ManagedTextAssetKind.CSV
    assert assets[1].subtitle == "1 wildcard"
    assert assets[1].metadata == (("Type", "CSV"),)


def test_wildcard_asset_text_lifecycle_preserves_file_content(
    tmp_path: Path,
) -> None:
    """Text saves, renames, and deletes should delegate safely."""

    service = _service(tmp_path)
    created = service.create_asset(
        CreateManagedTextAssetRequest(
            label="nested/animal",
            kind=ManagedTextAssetKind.PROMPT_TEXT,
            content="fox\n",
        )
    )

    saved = service.save_asset_text(created.id, "wolf\n")
    renamed = service.rename_asset(
        RenameManagedTextAssetRequest(asset_id=saved.id, label="animal")
    )

    assert renamed.id == "animal.txt"
    assert service.read_asset_text("animal.txt") == "wolf\n"

    service.delete_asset("animal.txt")

    assert service.list_assets() == ()


def test_wildcard_asset_renames_preserve_csv_suffix(tmp_path: Path) -> None:
    """CSV wildcard asset renames should keep the CSV storage suffix."""

    service = _service(tmp_path)
    created = service.create_asset(
        CreateManagedTextAssetRequest(label="people", kind=ManagedTextAssetKind.CSV)
    )

    renamed = service.rename_asset(
        RenameManagedTextAssetRequest(asset_id=created.id, label="nested/cast.txt")
    )

    assert renamed.id == "nested/cast.csv"
    assert service.read_asset_text("nested/cast.csv") == "value\n"


def test_wildcard_asset_adapter_rejects_traversal_through_repository(
    tmp_path: Path,
) -> None:
    """Traversal paths should remain rejected by existing wildcard persistence."""

    service = _service(tmp_path)

    with pytest.raises(ValueError):
        service.create_asset(
            CreateManagedTextAssetRequest(
                label="../escape",
                kind=ManagedTextAssetKind.PROMPT_TEXT,
            )
        )


def _service(tmp_path: Path) -> WildcardManagedTextAssetService:
    """Return a wildcard managed text asset service backed by a temp root."""

    return WildcardManagedTextAssetService(
        PromptWildcardFileManagementService(
            FilePromptWildcardFileRepository(tmp_path / "wildcards")
        )
    )
