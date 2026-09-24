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

"""Verify safe CivitAI version previews with current provider image shapes."""

from __future__ import annotations

from substitute.domain.civitai import CivitaiThumbnailSafetyPolicy
from substitute.domain.model_metadata import CivitaiThumbnailPolicy
from substitute.infrastructure.model_recommendations.civitai_payload_parser import (
    safe_version_thumbnail,
)


def test_version_preview_accepts_sfw_image_without_optional_provider_id() -> None:
    """Missing CivitAI image ID must not hide a safe real-version preview."""

    images = [
        {
            "type": "image",
            "url": "https://image.civitai.com/x/width=450/preview.jpeg",
            "nsfwLevel": 1,
            "width": 768,
            "height": 1024,
        }
    ]
    assert (
        safe_version_thumbnail(images, thumbnail_policy=CivitaiThumbnailPolicy())
        == "https://image.civitai.com/x/width=512/preview.jpeg"
    )


def test_version_preview_respects_safety_and_disabled_policy() -> None:
    """Racy, non-image, and disabled previews must never enter the timeline."""

    images = [
        {
            "type": "image",
            "url": "https://image.civitai.com/x/width=450/racy.jpeg",
            "nsfwLevel": 2,
            "width": 768,
            "height": 1024,
        },
        {
            "type": "video",
            "url": "https://image.civitai.com/x/width=450/video.jpeg",
            "nsfwLevel": 1,
            "width": 768,
            "height": 1024,
        },
    ]
    assert (
        safe_version_thumbnail(images, thumbnail_policy=CivitaiThumbnailPolicy())
        is None
    )
    assert (
        safe_version_thumbnail(
            images,
            thumbnail_policy=CivitaiThumbnailPolicy(
                CivitaiThumbnailSafetyPolicy.DISABLED
            ),
        )
        is None
    )
