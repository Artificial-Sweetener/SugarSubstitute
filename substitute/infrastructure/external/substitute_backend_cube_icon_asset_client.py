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

"""Fetch Cube Library icon assets from the active Substitute BackEnd target."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from substitute.application.ports import CubeIconAsset
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import default_http_get
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger(
    "infrastructure.external.substitute_backend_cube_icon_asset_client"
)
HttpGet = Callable[..., Any]


class SubstituteBackendCubeIconAssetClient:
    """Fetch validated cube icon assets from one active target endpoint."""

    def __init__(
        self,
        endpoint: ComfyEndpoint,
        *,
        http_get: HttpGet | None = None,
        timeout_seconds: float = 2.0,
    ) -> None:
        """Initialize the client with endpoint and injectable HTTP transport."""

        self._endpoint = endpoint
        self._http_get = http_get or default_http_get
        self._timeout_seconds = timeout_seconds

    def fetch_icon_asset(self, relative_url: str) -> CubeIconAsset | None:
        """Fetch one target-relative icon asset, returning ``None`` on failure."""

        absolute_url = self._asset_url(relative_url)
        if absolute_url is None:
            return None
        try:
            response = self._http_get(absolute_url, timeout=self._timeout_seconds)
            response.raise_for_status()
            content = response.content
            if not isinstance(content, bytes) or not content:
                return None
            return CubeIconAsset(
                content=content,
                media_type=_response_media_type(response.headers),
            )
        except Exception as error:
            log_warning(
                _LOGGER,
                "Cube Library icon asset fetch failed",
                endpoint=absolute_url,
                error=repr(error),
            )
            return None

    def _asset_url(self, relative_url: str) -> str | None:
        """Return an endpoint-rooted URL for a validated target-relative path."""

        normalized_url = relative_url.strip()
        if (
            not normalized_url.startswith("/")
            or normalized_url.startswith("//")
            or any(character.isspace() for character in normalized_url)
        ):
            return None
        return f"http://{self._endpoint.host}:{self._endpoint.port}{normalized_url}"


def _response_media_type(headers: object) -> str:
    """Return the normalized response content type without parameters."""

    if not isinstance(headers, dict):
        return ""
    content_type = headers.get("content-type") or headers.get("Content-Type")
    if not isinstance(content_type, str):
        return ""
    return content_type.split(";", maxsplit=1)[0].strip().lower()


__all__ = ["SubstituteBackendCubeIconAssetClient"]
