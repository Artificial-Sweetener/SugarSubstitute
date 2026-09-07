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

"""Verify bounded trusted-origin CivitAI thumbnail transport."""

from __future__ import annotations

import pytest

from substitute.infrastructure.model_recommendations import (
    CivitaiThumbnailFetcher,
    ThumbnailResponse,
)


def test_thumbnail_fetcher_accepts_only_bounded_civitai_images() -> None:
    """Return image bytes while forwarding the configured transport bounds."""

    calls: list[tuple[str, float, int]] = []

    def transport(url: str, *, timeout: float, maximum_bytes: int) -> ThumbnailResponse:
        """Record one trusted request and return a small image payload."""

        calls.append((url, timeout, maximum_bytes))
        return ThumbnailResponse("image/png", b"png")

    fetcher = CivitaiThumbnailFetcher(
        transport=transport,
        timeout_seconds=3.0,
        maximum_bytes=8,
    )

    assert fetcher.fetch("https://image.civitai.com/example.png") == b"png"
    assert calls == [("https://image.civitai.com/example.png", 3.0, 8)]


@pytest.mark.parametrize(
    ("url", "response"),
    (
        ("http://image.civitai.com/a.png", ThumbnailResponse("image/png", b"x")),
        ("https://example.com/a.png", ThumbnailResponse("image/png", b"x")),
        ("https://image.civitai.com/a.png", ThumbnailResponse("text/html", b"x")),
        ("https://image.civitai.com/a.png", ThumbnailResponse("image/png", b"")),
        ("https://image.civitai.com/a.png", ThumbnailResponse("image/png", b"12345")),
    ),
)
def test_thumbnail_fetcher_rejects_untrusted_or_invalid_payloads(
    url: str,
    response: ThumbnailResponse,
) -> None:
    """Fail closed for origin, media-type, empty, and oversized violations."""

    fetcher = CivitaiThumbnailFetcher(
        transport=lambda *_args, **_kwargs: response,
        maximum_bytes=4,
    )

    with pytest.raises(ValueError):
        fetcher.fetch(url)
