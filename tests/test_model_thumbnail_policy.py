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

"""Tests for CivitAI default thumbnail selection policy."""

from __future__ import annotations

from substitute.domain.model_metadata import (
    CivitaiImage,
    CivitaiModelVersion,
    FirstSfwThumbnailPolicy,
    ThumbnailSelectionStatus,
)


def test_first_sfw_thumbnail_policy_selects_first_safe_image() -> None:
    """Policy should skip unsafe images and select the first SFW image."""

    unsafe = _image("https://example.test/unsafe.jpg", nsfw=True)
    safe = _image("https://example.test/safe.jpg", nsfw=False, nsfw_level="None")

    selection = FirstSfwThumbnailPolicy().select(_version((unsafe, safe)))

    assert selection.status is ThumbnailSelectionStatus.SELECTED
    assert selection.image == safe
    assert selection.policy == "first-sfw-version-image"


def test_first_sfw_thumbnail_policy_skips_videos_and_soft_mature_x_images() -> None:
    """Policy should not use videos or NSFW-level images as defaults."""

    candidates = (
        _image("https://example.test/video.mp4", image_type="video"),
        _image("https://example.test/soft.jpg", nsfw_level="Soft"),
        _image("https://example.test/mature.jpg", nsfw_level="Mature"),
        _image("https://example.test/x.jpg", nsfw_level="X"),
        _image("https://example.test/safe.jpg", nsfw_level=0),
    )

    selection = FirstSfwThumbnailPolicy().select(_version(candidates))

    assert selection.status is ThumbnailSelectionStatus.SELECTED
    assert selection.image is candidates[-1]


def test_first_sfw_thumbnail_policy_treats_civitai_numeric_none_as_safe() -> None:
    """CivitAI numeric NSFW level 1 represents the SFW ``None`` level."""

    image = _image("https://example.test/safe.jpg", nsfw_level=1)

    selection = FirstSfwThumbnailPolicy().select(_version((image,)))

    assert selection.status is ThumbnailSelectionStatus.SELECTED
    assert selection.image == image


def test_first_sfw_thumbnail_policy_returns_no_candidate_when_only_nsfw() -> None:
    """Policy should return no thumbnail when no safe image exists."""

    selection = FirstSfwThumbnailPolicy().select(
        _version(
            (
                _image("https://example.test/soft.jpg", nsfw_level="Soft"),
                _image("https://example.test/flagged.jpg", nsfw=True),
            )
        )
    )

    assert selection.status is ThumbnailSelectionStatus.NO_SFW_IMAGE
    assert selection.image is None


def test_first_sfw_thumbnail_policy_allows_missing_nsfw_fields() -> None:
    """Missing NSFW fields should be treated as SFW for first-version policy."""

    image = _image("https://example.test/unknown.jpg")

    selection = FirstSfwThumbnailPolicy().select(_version((image,)))

    assert selection.status is ThumbnailSelectionStatus.SELECTED
    assert selection.image == image


def _image(
    url: str,
    *,
    image_type: str | None = "image",
    nsfw: bool | None = None,
    nsfw_level: str | int | None = None,
) -> CivitaiImage:
    """Build a normalized image candidate for tests."""

    return CivitaiImage(
        image_id=None,
        url=url,
        image_type=image_type,
        nsfw=nsfw,
        nsfw_level=nsfw_level,
        width=None,
        height=None,
        meta=None,
    )


def _version(images: tuple[CivitaiImage, ...]) -> CivitaiModelVersion:
    """Build a normalized model version with supplied image candidates."""

    return CivitaiModelVersion(
        model_id=1,
        model_version_id=2,
        model_name="Model",
        model_type="LORA",
        version_name="v1",
        base_model="SDXL",
        trained_words=("trigger",),
        description=None,
        version_description=None,
        tags=(),
        creator_username=None,
        creator_image=None,
        nsfw=False,
        nsfw_level=None,
        availability=None,
        files=(),
        images=images,
        stats={},
        model_page_url="https://civitai.com/models/1?modelVersionId=2",
        source_url="https://civitai.com/api/v1/model-versions/by-hash/abc",
        fetched_at="2026-04-14T00:00:00Z",
        raw_provider_payload={},
    )
