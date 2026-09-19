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

"""Fetch bounded CivitAI recommendation thumbnails through system trust."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import ssl
from urllib.parse import urlparse
import urllib.request

from sugarsubstitute_shared.tls import SystemTrustTlsContext

_MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ThumbnailResponse:
    """Carry sanitized HTTP image response fields into validation."""

    content_type: str
    payload: bytes


ThumbnailTransport = Callable[..., ThumbnailResponse]


class CivitaiThumbnailFetcher:
    """Download only bounded image payloads from CivitAI-owned HTTPS hosts."""

    def __init__(
        self,
        *,
        transport: ThumbnailTransport | None = None,
        timeout_seconds: float = 10.0,
        maximum_bytes: int = _MAX_THUMBNAIL_BYTES,
    ) -> None:
        """Store bounded image transport policy."""

        if timeout_seconds <= 0 or maximum_bytes < 1:
            raise ValueError("Thumbnail transport limits must be positive.")
        self._transport = transport or _fetch_thumbnail
        self._timeout_seconds = timeout_seconds
        self._maximum_bytes = maximum_bytes

    def fetch(self, url: str) -> bytes:
        """Return a validated image payload or raise a sanitized failure."""

        if not _is_civitai_asset_url(url):
            raise ValueError("Thumbnail URL is outside the trusted CivitAI origin.")
        response = self._transport(
            url,
            timeout=self._timeout_seconds,
            maximum_bytes=self._maximum_bytes,
        )
        if not response.content_type.casefold().startswith("image/"):
            raise ValueError("Thumbnail response is not an image.")
        if not response.payload or len(response.payload) > self._maximum_bytes:
            raise ValueError("Thumbnail response size is outside policy.")
        return response.payload


def _fetch_thumbnail(
    url: str,
    *,
    timeout: float,
    maximum_bytes: int,
    tls_context: ssl.SSLContext | None = None,
) -> ThumbnailResponse:
    """Fetch a bounded thumbnail and reject oversized streams before decoding."""

    request = urllib.request.Request(
        url,
        headers={"Accept": "image/*", "User-Agent": "SugarSubstitute/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(  # noqa: S310 - caller validates trusted HTTPS host.
        request,
        timeout=timeout,
        context=tls_context or SystemTrustTlsContext.create(),
    ) as response:
        declared = response.headers.get("Content-Length")
        if declared is not None and int(declared) > maximum_bytes:
            raise ValueError("Thumbnail response exceeds the configured size limit.")
        payload = response.read(maximum_bytes + 1)
        return ThumbnailResponse(
            content_type=response.headers.get_content_type(),
            payload=payload,
        )


def _is_civitai_asset_url(value: str) -> bool:
    """Return whether an HTTPS asset uses CivitAI's domain."""

    parsed = urlparse(value)
    hostname = parsed.hostname or ""
    return parsed.scheme == "https" and (
        hostname == "civitai.com" or hostname.endswith(".civitai.com")
    )


__all__ = ["CivitaiThumbnailFetcher", "ThumbnailResponse", "ThumbnailTransport"]
