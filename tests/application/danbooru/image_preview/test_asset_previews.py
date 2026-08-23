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

"""Test cached Danbooru media-asset preview variant selection."""

from __future__ import annotations

from pathlib import Path

from substitute.application.danbooru.content_models import DanbooruImagePreviewState
from substitute.domain.danbooru import (
    DanbooruLookupStatus,
    DanbooruMediaAssetLookupResult,
)
from tests.application.danbooru.image_preview.collaborators import (
    StubDanbooruImagePreviewClient,
    asset_variant,
    build_image_preview_service,
    media_asset_record,
)


def test_chooses_smallest_asset_variant_covering_target_height(
    tmp_path: Path,
) -> None:
    """Choose and cache the smallest asset variant at least 156 pixels tall."""

    chosen_url = "https://cdn.donmai.us/360x360/example-asset.jpg"
    client = StubDanbooruImagePreviewClient(
        post_results_by_id={},
        media_asset_results_by_id={
            37448022: DanbooruMediaAssetLookupResult(
                status=DanbooruLookupStatus.FOUND,
                media_asset=media_asset_record(
                    asset_id=37448022,
                    image_width=1280,
                    image_height=720,
                    variants=(
                        asset_variant(
                            variant_type="180x180",
                            url="https://cdn.donmai.us/180x180/example-asset.jpg",
                            width=180,
                            height=101,
                        ),
                        asset_variant(
                            variant_type="360x360",
                            url=chosen_url,
                            width=360,
                            height=203,
                        ),
                        asset_variant(
                            variant_type="sample",
                            url="https://cdn.donmai.us/sample/example-asset.jpg",
                            width=850,
                            height=478,
                        ),
                        asset_variant(
                            variant_type="original",
                            url="https://cdn.donmai.us/original/example-asset.jpg",
                            width=1280,
                            height=720,
                        ),
                    ),
                ),
            )
        },
        binary_payloads_by_url={chosen_url: b"asset-image-bytes"},
    )
    service = build_image_preview_service(tmp_path, client=client)

    first = service.resolve_preview_for_reference(
        source_kind="asset",
        source_id=37448022,
    )
    second = service.resolve_preview_for_reference(
        source_kind="asset",
        source_id=37448022,
    )

    assert first.state is DanbooruImagePreviewState.READY
    assert first.local_path is not None
    assert first.local_path.read_bytes() == b"asset-image-bytes"
    assert (first.width, first.height) == (360, 203)
    assert second.state is DanbooruImagePreviewState.READY
    assert client.calls == [("asset", "37448022"), ("binary", chosen_url)]


def test_prefers_asset_sample_when_smaller_variants_are_too_short(
    tmp_path: Path,
) -> None:
    """Fall back to the sample before the original when small variants miss."""

    sample_url = "https://cdn.donmai.us/sample/example-asset.jpg"
    client = StubDanbooruImagePreviewClient(
        post_results_by_id={},
        media_asset_results_by_id={
            400: DanbooruMediaAssetLookupResult(
                status=DanbooruLookupStatus.FOUND,
                media_asset=media_asset_record(
                    asset_id=400,
                    image_width=2100,
                    image_height=700,
                    variants=(
                        asset_variant(
                            variant_type="180x180",
                            url="https://cdn.donmai.us/180x180/example-asset.jpg",
                            width=180,
                            height=60,
                        ),
                        asset_variant(
                            variant_type="360x360",
                            url="https://cdn.donmai.us/360x360/example-asset.jpg",
                            width=360,
                            height=120,
                        ),
                        asset_variant(
                            variant_type="720x720",
                            url="https://cdn.donmai.us/720x720/example-asset.webp",
                            width=720,
                            height=140,
                        ),
                        asset_variant(
                            variant_type="sample",
                            url=sample_url,
                            width=850,
                            height=283,
                        ),
                        asset_variant(
                            variant_type="original",
                            url="https://cdn.donmai.us/original/example-asset.jpg",
                            width=2100,
                            height=700,
                        ),
                    ),
                ),
            )
        },
        binary_payloads_by_url={sample_url: b"sample-asset-image-bytes"},
    )
    service = build_image_preview_service(tmp_path, client=client)

    result = service.resolve_preview_for_reference(source_kind="asset", source_id=400)

    assert result.state is DanbooruImagePreviewState.READY
    assert result.local_path is not None
    assert result.local_path.read_bytes() == b"sample-asset-image-bytes"
    assert client.calls == [("asset", "400"), ("binary", sample_url)]
