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

"""Verify packaged Ultralytics thumbnail repository behavior."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.model_metadata.ultralytics_visual_catalog import (
    BUNDLED_ULTRALYTICS_BANNER_STORAGE_PREFIX,
    BUNDLED_ULTRALYTICS_STORAGE_PREFIX,
    bundled_ultralytics_asset_names,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.infrastructure.model_thumbnails import (
    BundledUltralyticsThumbnailRepository,
    LayeredThumbnailAssetRepository,
)


def test_every_declared_bundled_asset_decodes_to_a_qt_thumbnail() -> None:
    """The shipped catalog must not reference missing or unreadable resources."""

    repository = BundledUltralyticsThumbnailRepository()

    for asset_name in bundled_ultralytics_asset_names():
        asset = repository.read_thumbnail_asset(
            f"{BUNDLED_ULTRALYTICS_STORAGE_PREFIX}{asset_name}"
        )
        assert asset is not None
        assert (asset.width, asset.height) == (512, 512)
        assert len(asset.payload) == asset.bytes_per_line * asset.height


def test_bundled_repository_rejects_unknown_and_unrelated_keys() -> None:
    """Only allow the fixed resource inventory through the packaged adapter."""

    repository = BundledUltralyticsThumbnailRepository()

    assert repository.read_thumbnail_asset("civitai:thumbnail:123") is None
    assert (
        repository.read_thumbnail_asset(
            f"{BUNDLED_ULTRALYTICS_STORAGE_PREFIX}../not-an-asset"
        )
        is None
    )


def test_banner_variant_applies_a_charcoal_legibility_wash() -> None:
    """Closed picker artwork should not depend on a lucky dark center crop."""

    repository = BundledUltralyticsThumbnailRepository()
    standard = repository.read_thumbnail_asset(
        f"{BUNDLED_ULTRALYTICS_STORAGE_PREFIX}face-detection"
    )
    banner = repository.read_thumbnail_asset(
        f"{BUNDLED_ULTRALYTICS_BANNER_STORAGE_PREFIX}face-detection"
    )

    assert standard is not None
    assert banner is not None
    assert banner.payload != standard.payload
    assert (banner.width, banner.height) == (standard.width, standard.height)


def test_layered_repository_preserves_existing_thumbnail_storage() -> None:
    """Bundled lookup should fall through to the existing authoritative store."""

    expected = ThumbnailAsset(
        storage_key="existing",
        width=1,
        height=1,
        qt_format=1,
        bytes_per_line=4,
        content_format="test",
        payload=b"\x00\x00\x00\x00",
    )
    primary = _RecordingRepository({"existing": expected})
    layered = LayeredThumbnailAssetRepository(
        (BundledUltralyticsThumbnailRepository(), primary)
    )

    assert layered.read_thumbnail_asset("existing") is expected
    assert primary.keys == ["existing"]


@dataclass
class _RecordingRepository:
    """Record lookup keys while serving deterministic assets."""

    assets: dict[str, ThumbnailAsset]

    def __post_init__(self) -> None:
        """Initialize the lookup log."""

        self.keys: list[str] = []

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Return one configured asset and record the request."""

        self.keys.append(storage_key)
        return self.assets.get(storage_key)
