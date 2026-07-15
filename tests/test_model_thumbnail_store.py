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

"""Tests for remote CivitAI thumbnail download failure handling."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import requests

from substitute.domain.model_metadata import CivitaiImage
from substitute.infrastructure.persistence.model_thumbnail_store import (
    ModelThumbnailStore,
)


def test_thumbnail_store_skips_repeated_not_found_image_urls(tmp_path: Path) -> None:
    """A CivitAI 404 should be remembered for the lifetime of the thumbnail store."""

    calls: list[str] = []

    def http_get(url: str, *, timeout: float) -> object:
        """Return a response whose status check reports the missing image URL."""

        _ = timeout
        calls.append(url)
        return _NotFoundResponse()

    store = ModelThumbnailStore(tmp_path, http_get=http_get)
    image = CivitaiImage(
        image_id=42,
        url="https://image.civitai.com/missing.jpeg",
        image_type="image",
        nsfw=False,
        nsfw_level=0,
        width=512,
        height=512,
        meta=None,
    )

    assert (
        store.cache_thumbnail(
            sha256="a" * 64,
            image=image,
            selection_policy="first_sfw",
        )
        is None
    )
    assert (
        store.cache_thumbnail(
            sha256="b" * 64,
            image=image,
            selection_policy="first_sfw",
        )
        is None
    )

    assert calls == [image.url]


class _NotFoundResponse:
    """Raise a Requests HTTP error with an attached 404 response."""

    def raise_for_status(self) -> None:
        """Report the configured response as a permanently missing image."""

        error = requests.HTTPError("404 Client Error")
        error.response = cast(requests.Response, SimpleNamespace(status_code=404))
        raise error
