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

"""HTTP client for Substitute BackEnd preview asset routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from substitute.domain.common import JsonObject
from substitute.domain.generation import (
    TaesdPreviewAsset,
    TaesdPreviewAssetState,
    TaesdPreviewAssetStatus,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import (
    default_http_get,
    default_http_post,
    is_request_exception,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.external.substitute_backend_preview_assets_client")
HttpGet = Callable[..., Any]
HttpPost = Callable[..., Any]


class SubstituteBackendPreviewAssetsClient:
    """Query Substitute BackEnd preview asset preparation routes."""

    def __init__(
        self,
        endpoint: ComfyEndpoint,
        *,
        http_get: HttpGet | None = None,
        http_post: HttpPost | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize the client with endpoint and injectable HTTP transport."""

        self._endpoint = endpoint
        self._http_get = http_get or default_http_get
        self._http_post = http_post or default_http_post
        self._timeout_seconds = timeout_seconds

    def get_taesd_status(self) -> TaesdPreviewAssetStatus | None:
        """Return TAESD asset readiness or ``None`` when unavailable."""

        payload = self._get_json("/substitute/v1/preview-assets/taesd/status")
        return _parse_optional_status(payload, "TAESD status")

    def ensure_taesd_assets(self) -> TaesdPreviewAssetStatus | None:
        """Ask the backend to prepare missing TAESD assets."""

        payload = self._post_json("/substitute/v1/preview-assets/taesd/ensure", {})
        return _parse_optional_status(payload, "TAESD ensure")

    def _get_json(self, path: str) -> JsonObject | None:
        """GET one backend route and return a JSON object on success."""

        try:
            response = self._http_get(self._url(path), timeout=self._timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not _is_expected_http_error(error):
                raise
            log_warning(
                _LOGGER,
                "Substitute BackEnd preview asset GET failed",
                endpoint=self._url(path),
                error=repr(error),
            )
            return None
        if not isinstance(payload, dict):
            log_warning(
                _LOGGER,
                "Substitute BackEnd preview asset GET returned non-object JSON",
                endpoint=self._url(path),
            )
            return None
        return payload

    def _post_json(self, path: str, body: JsonObject) -> JsonObject | None:
        """POST one backend route and return a JSON object on success."""

        try:
            response = self._http_post(
                self._url(path),
                json=body,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not _is_expected_http_error(error):
                raise
            log_warning(
                _LOGGER,
                "Substitute BackEnd preview asset POST failed",
                endpoint=self._url(path),
                error=repr(error),
            )
            return None
        if not isinstance(payload, dict):
            log_warning(
                _LOGGER,
                "Substitute BackEnd preview asset POST returned non-object JSON",
                endpoint=self._url(path),
            )
            return None
        return payload

    def _url(self, path: str) -> str:
        """Return an HTTP URL rooted at the configured Comfy endpoint."""

        return f"http://{self._endpoint.host}:{self._endpoint.port}{path}"


def _parse_optional_status(
    payload: JsonObject | None,
    operation: str,
) -> TaesdPreviewAssetStatus | None:
    """Parse an optional TAESD status payload with operation-specific logging."""

    if payload is None:
        return None
    try:
        return _parse_status(payload)
    except ValueError as error:
        log_warning(
            _LOGGER,
            f"Invalid Substitute BackEnd preview asset {operation} response",
            error=repr(error),
        )
        return None


def _is_expected_http_error(error: BaseException) -> bool:
    """Return whether an HTTP operation failure should be converted to `None`."""

    return isinstance(error, TypeError | ValueError) or is_request_exception(error)


def _parse_status(data: JsonObject) -> TaesdPreviewAssetStatus:
    """Parse one TAESD asset readiness payload."""

    return TaesdPreviewAssetStatus(
        schema_version=_required_int(data, "schemaVersion"),
        ready=_read_bool(data, "ready"),
        installed_count=_required_int(data, "installedCount"),
        missing_count=_required_int(data, "missingCount"),
        downloads_attempted=_read_bool(data, "downloadsAttempted"),
        destination_root=_read_str(data, "destinationRoot"),
        assets=_parse_assets(data.get("assets")),
    )


def _parse_assets(value: object) -> tuple[TaesdPreviewAsset, ...]:
    """Parse TAESD asset records from the backend payload."""

    if not isinstance(value, list):
        raise ValueError("assets must be a list")
    assets: list[TaesdPreviewAsset] = []
    for raw_asset in value:
        if not isinstance(raw_asset, dict):
            raise ValueError("asset entries must be objects")
        assets.append(_parse_asset(raw_asset))
    return tuple(assets)


def _parse_asset(data: JsonObject) -> TaesdPreviewAsset:
    """Parse one TAESD asset record."""

    return TaesdPreviewAsset(
        asset_id=_required_str(data, "id"),
        filename=_required_str(data, "filename"),
        url=_required_str(data, "url"),
        status=_parse_asset_state(_required_str(data, "status")),
        path=_read_str(data, "path"),
        size_bytes=_read_int(data, "sizeBytes"),
        error=_read_str(data, "error"),
    )


def _parse_asset_state(value: str) -> TaesdPreviewAssetState:
    """Parse a backend asset status value."""

    try:
        return TaesdPreviewAssetState(value)
    except ValueError as error:
        raise ValueError(f"unknown asset status: {value}") from error


def _required_str(data: JsonObject, key: str) -> str:
    """Read a required string field."""

    value = _read_str(data, key)
    if value is None:
        raise ValueError(f"{key} must be a string")
    return value


def _read_str(data: JsonObject, key: str) -> str | None:
    """Read an optional string field."""

    value = data.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _required_int(data: JsonObject, key: str) -> int:
    """Read a required integer field."""

    value = _read_int(data, key)
    if value is None:
        raise ValueError(f"{key} must be an integer")
    return value


def _read_int(data: JsonObject, key: str) -> int | None:
    """Read an optional integer field."""

    value = data.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _read_bool(data: JsonObject, key: str) -> bool:
    """Read an optional boolean field with a false default."""

    value = data.get(key)
    return value if isinstance(value, bool) else False


__all__ = ["SubstituteBackendPreviewAssetsClient"]
