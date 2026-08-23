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

"""Verify remote and local model-thumbnail admission and encoding contracts."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QImage

from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_HEIGHT,
    BANNER_THUMBNAIL_ROLE,
    BANNER_THUMBNAIL_SIZE,
    BANNER_THUMBNAIL_WIDTH,
    STANDARD_THUMBNAIL_ROLE,
)
from substitute.infrastructure.persistence import ModelThumbnailStore
from tests.infrastructure.persistence.model_metadata.support import (
    FakeImageResponse,
    image,
    image_from_asset,
)


def test_thumbnail_store_writes_images_and_rejects_non_images(tmp_path: Path) -> None:
    """Thumbnail store should download only image content."""

    calls: list[str] = []

    def fake_get(url: str, **_kwargs: object) -> FakeImageResponse:
        """Return fake image or text responses by URL."""

        calls.append(url)
        if url.endswith(".txt"):
            return FakeImageResponse(content_type="text/plain", content=b"text")
        return FakeImageResponse(content_type="image/jpeg")

    store = ModelThumbnailStore(
        http_get=fake_get,
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    cached = store.cache_thumbnail(
        sha256="abc123",
        image=image("https://image.example/safe.jpg"),
        selection_policy="first-sfw-version-image",
    )
    rejected = store.cache_thumbnail(
        sha256="def456",
        image=image("https://image.example/not-image.txt"),
        selection_policy="first-sfw-version-image",
    )

    assert cached is not None
    assert [(variant.role, variant.size) for variant in cached.variants] == [
        (STANDARD_THUMBNAIL_ROLE, 128),
        (STANDARD_THUMBNAIL_ROLE, 256),
        (STANDARD_THUMBNAIL_ROLE, 512),
        (BANNER_THUMBNAIL_ROLE, BANNER_THUMBNAIL_SIZE),
    ]
    assert cached.variants[0].storage_key == "ABC123:standard:128"
    assert cached.variants[0].width == 85
    assert cached.variants[0].height == 128
    assert cached.variants[-1].storage_key == "ABC123:banner:768x160"
    assert cached.variants[-1].width == BANNER_THUMBNAIL_WIDTH
    assert cached.variants[-1].height == BANNER_THUMBNAIL_HEIGHT
    assert image_from_asset(cached.assets[0]) is not None
    assert image_from_asset(cached.assets[-1]) is not None
    assert rejected is None
    assert calls == [
        "https://image.example/safe.jpg",
        "https://image.example/not-image.txt",
    ]


def test_thumbnail_store_caches_local_output_thumbnail(tmp_path: Path) -> None:
    """Thumbnail store should prepare standard and banner variants from a local image."""

    _ = tmp_path
    store = ModelThumbnailStore(clock=lambda: "2026-07-03T12:00:00Z")
    local_image = QImage(96, 64, QImage.Format.Format_ARGB32)
    local_image.fill(QColor("#336699"))

    cached = store.cache_local_thumbnail(
        sha256="abc123",
        image=local_image,
        source="output_canvas",
        source_label="C:/outputs/image.png",
    )

    assert cached is not None
    assert cached.source == "output_canvas"
    assert cached.selection_policy == "user_selected_output_canvas"
    assert cached.source_image_url == "C:/outputs/image.png"
    assert cached.source_image_id is None
    assert cached.variants[0].storage_key == "ABC123:standard:128"
    assert cached.variants[-1].storage_key == "ABC123:banner:768x160"
    assert image_from_asset(cached.assets[0]) is not None
    assert image_from_asset(cached.assets[-1]) is not None


def test_thumbnail_store_rejects_null_local_output_thumbnail(tmp_path: Path) -> None:
    """Thumbnail store should reject null local images."""

    _ = tmp_path
    store = ModelThumbnailStore()

    rejected = store.cache_local_thumbnail(
        sha256="abc123",
        image=QImage(),
        source="output_canvas",
        source_label="C:/outputs/missing.png",
    )

    assert rejected is None


def test_thumbnail_store_accepts_image_url_when_content_type_is_missing(
    tmp_path: Path,
) -> None:
    """Thumbnail store should accept CivitAI image URLs when headers omit content type."""

    _ = tmp_path

    def fake_get(_url: str, **_kwargs: object) -> FakeImageResponse:
        """Return a response with a missing content type."""

        return FakeImageResponse(content_type="")

    store = ModelThumbnailStore(
        http_get=fake_get,
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    cached = store.cache_thumbnail(
        sha256="abc123",
        image=image(
            "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/example/original=true/87798219.jpeg"
        ),
        selection_policy="first-sfw-version-image",
    )

    assert cached is not None
    assert cached.variants[0].storage_key == "ABC123:standard:128"
    assert image_from_asset(cached.assets[0]) is not None


def test_thumbnail_store_accepts_octet_stream_when_payload_decodes(
    tmp_path: Path,
) -> None:
    """Thumbnail store should accept CivitAI images served as octet streams."""

    _ = tmp_path

    def fake_get(_url: str, **_kwargs: object) -> FakeImageResponse:
        """Return a decodable image response with a generic binary content type."""

        return FakeImageResponse(content_type="binary/octet-stream")

    store = ModelThumbnailStore(
        http_get=fake_get,
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    cached = store.cache_thumbnail(
        sha256="abc123",
        image=image(
            "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/example/original=true/39128512.jpeg"
        ),
        selection_policy="first-sfw-version-image",
    )

    assert cached is not None
    assert cached.variants[0].storage_key == "ABC123:standard:128"
    assert image_from_asset(cached.assets[0]) is not None


def test_thumbnail_store_accepts_text_plain_when_payload_decodes(
    tmp_path: Path,
) -> None:
    """Thumbnail store should accept CivitAI images served with text headers."""

    _ = tmp_path

    def fake_get(_url: str, **_kwargs: object) -> FakeImageResponse:
        """Return a decodable image response with a misleading text content type."""

        return FakeImageResponse(content_type="text/plain")

    store = ModelThumbnailStore(
        http_get=fake_get,
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    cached = store.cache_thumbnail(
        sha256="abc123",
        image=image(
            "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/example/original=true/461741.jpeg"
        ),
        selection_policy="first-sfw-version-image",
    )

    assert cached is not None
    assert cached.variants[0].storage_key == "ABC123:standard:128"
    assert image_from_asset(cached.assets[0]) is not None


def test_thumbnail_store_rejects_text_plain_when_payload_does_not_decode(
    tmp_path: Path,
) -> None:
    """Thumbnail store should reject mislabeled payloads that are not images."""

    _ = tmp_path

    def fake_get(_url: str, **_kwargs: object) -> FakeImageResponse:
        """Return an undecodable payload with a text content type."""

        return FakeImageResponse(content_type="text/plain", content=b"text")

    store = ModelThumbnailStore(
        http_get=fake_get,
        clock=lambda: "2026-04-14T12:00:00Z",
    )

    rejected = store.cache_thumbnail(
        sha256="abc123",
        image=image("https://image.civitai.com/not-an-image.txt"),
        selection_policy="first-sfw-version-image",
    )

    assert rejected is None
